"""Voice chat endpoint: audio in, audio out.

This is a convenience wrapper for a single-turn voice interaction:

    audio -> STT -> DeepTutor chat (with optional persona) -> TTS -> audio

It reuses DeepTutor's configured TTS/STT providers and the application
service's durable chat turn.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

from deeptutor.app import DeepTutorApp, TurnRequest
from deeptutor.services.voice import VoiceProviderError, synthesize_speech, transcribe_audio
from deeptutor.services.voice.base import VoiceProviderTimeout

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB, matching /api/voice/stt


def _collect_text(events: list[dict[str, Any]]) -> str:
    """Pick the assistant's final answer text out of a streamed turn."""
    round_buffers: dict[str, str] = {}
    round_order: list[str] = []
    legacy_buffer = ""

    for item in events:
        if item.get("type") != "content":
            continue
        metadata = item.get("metadata") or {}
        text = str(item.get("content", "") or "")
        if not text:
            continue
        call_id = str(metadata.get("call_id") or "")
        trace_kind = str(metadata.get("trace_kind") or "")
        if call_id and trace_kind == "llm_chunk":
            round_buffers.setdefault(call_id, "")
            if call_id not in round_order:
                round_order.append(call_id)
            round_buffers[call_id] += text
            continue
        if trace_kind == "llm_output":
            parts: list[str] = []
            for cid in list(round_order):
                buf = round_buffers.pop(cid, "")
                if buf:
                    parts.append(buf)
            round_order.clear()
            if text:
                parts.append(text)
            return "\n".join(parts).strip()
        legacy_buffer += text

    parts: list[str] = []
    for cid in list(round_order):
        buf = round_buffers.pop(cid, "")
        if buf:
            parts.append(buf)
    if legacy_buffer:
        parts.append(legacy_buffer)
    return "\n".join(parts).strip()


async def _run_chat_turn(
    app: DeepTutorApp,
    transcript: str,
    *,
    persona: str | None,
    session_id: str | None,
    language: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Run a chat turn and return (session, turn, reply_text)."""
    events: list[dict[str, Any]] = []

    turn_request = TurnRequest(
        content=transcript,
        capability="chat",
        persona=persona,
        session_id=session_id,
        language=language,
    )
    session, turn = await app.start_turn(turn_request)

    async for item in app.stream_turn(turn["id"]):
        events.append(item)
        # Auto-resolve any ask_user pause so headless callers do not hang.
        if item.get("type") == "tool_result":
            ask = (item.get("metadata") or {}).get("ask_user")
            if isinstance(ask, dict) and ask:
                await app.submit_user_reply(turn["id"], text="")

    reply_text = _collect_text(events)
    return session, turn, reply_text


@router.post("/chat", response_model=None)
async def voice_chat(
    request: Request,
    audio: UploadFile = File(...),
    persona: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    output: Literal["json", "audio"] = Query(
        default="json",
        description='Return format: "json" (default, with base64 audio) or "audio" (raw audio stream).',
    ),
) -> JSONResponse | StreamingResponse:
    """Accept an audio clip, transcribe it, ask DeepTutor, and return TTS audio.

    Set ``output=audio`` to receive the reply as a raw audio stream (easier
    for mobile/WebRTC clients).  The default ``output=json`` also returns the
    transcript and reply text for UI display.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio upload.")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio exceeds the 25 MB limit.",
        )

    # 1. Speech-to-text
    try:
        transcript = await transcribe_audio(
            audio_bytes,
            filename=audio.filename or "audio.webm",
            content_type=audio.content_type or "application/octet-stream",
            language=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except VoiceProviderTimeout as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except VoiceProviderError as exc:
        logger.warning("STT provider error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if not transcript or not transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Speech could not be transcribed.",
        )

    # 2. DeepTutor chat turn
    try:
        from deeptutor.services.workspace.context import current_workspace_id

        workspace_id = current_workspace_id()
    except Exception:
        workspace_id = None

    app = DeepTutorApp(workspace_id=workspace_id)
    try:
        session, turn, reply_text = await _run_chat_turn(
            app,
            transcript,
            persona=persona,
            session_id=session_id,
            language=language,
        )
    except Exception as exc:
        logger.exception("DeepTutor turn failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DeepTutor processing failed: {exc}",
        ) from exc

    if not reply_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DeepTutor returned an empty response.",
        )

    # 3. Text-to-speech
    try:
        audio_out, content_type = await synthesize_speech(reply_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except VoiceProviderTimeout as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except VoiceProviderError as exc:
        logger.warning("TTS provider error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if output == "audio":
        # Return the raw audio stream; metadata travels in headers for clients
        # that just want to play the audio directly.
        return StreamingResponse(
            io.BytesIO(audio_out),
            media_type=content_type,
            headers={
                "X-Session-Id": str(session.get("id", "")),
                "X-Turn-Id": str(turn.get("id", "")),
                "X-Transcript": base64.b64encode(transcript.strip().encode("utf-8")).decode("ascii"),
                "X-Reply": base64.b64encode(reply_text.strip().encode("utf-8")).decode("ascii"),
                "Cache-Control": "no-store",
            },
        )

    return JSONResponse(
        content={
            "session_id": str(session.get("id", "")),
            "turn_id": str(turn.get("id", "")),
            "transcript": transcript.strip(),
            "reply": reply_text.strip(),
            "audio_base64": base64.b64encode(audio_out).decode("ascii"),
            "audio_content_type": content_type,
        },
        headers={"Cache-Control": "no-store"},
    )
