"""Voice chat endpoints: audio in, audio/text out.

    audio -> STT -> DeepTutor chat -> {text, audio}
"""

from __future__ import annotations

import base64
import io
import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

from deeptutor.app import DeepTutorApp, TurnRequest
from deeptutor.services.voice import VoiceProviderError, synthesize_speech, transcribe_audio

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

_MAX_AUDIO_BYTES = 25 * 1024 * 1024
_MAX_REPLY_CHARS = 140


def _collect_text(events: list[dict[str, Any]]) -> str:
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
        if item.get("type") == "tool_result":
            ask = (item.get("metadata") or {}).get("ask_user")
            if isinstance(ask, dict) and ask:
                await app.submit_user_reply(turn["id"], text="")

    reply_text = _collect_text(events)
    return session, turn, reply_text


async def _read_and_validate_audio(audio: UploadFile) -> bytes:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio upload.")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio exceeds the 25 MB limit.",
        )
    return audio_bytes


async def _transcribe_for_chat(audio_bytes: bytes, audio: UploadFile, language: str | None) -> str:
    try:
        return await transcribe_audio(
            audio_bytes,
            filename=audio.filename or "audio.webm",
            content_type=audio.content_type or "application/octet-stream",
            language=language,
        )
    except VoiceProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


async def _chat_reply(
    transcript: str,
    *,
    persona: str | None,
    session_id: str | None,
    language: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if not transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Speech could not be transcribed.",
        )

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

    reply_text = reply_text.strip()
    if len(reply_text) > _MAX_REPLY_CHARS:
        reply_text = reply_text[:_MAX_REPLY_CHARS].rsplit("，", 1)[0] + "…"
    return session, turn, reply_text


@router.post("/chat/text")
async def voice_chat_text(
    request: Request,
    audio: UploadFile = File(...),
    persona: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
) -> JSONResponse:
    """Audio -> STT -> DeepTutor chat. Returns text only (fast)."""
    t0 = time.monotonic()
    audio_bytes = await _read_and_validate_audio(audio)
    transcript = await _transcribe_for_chat(audio_bytes, audio, language)
    logger.info("voice_chat_text: STT done in %.2fs, transcript=%r", time.monotonic() - t0, transcript[:60])

    t1 = time.monotonic()
    session, turn, reply_text = await _chat_reply(
        transcript,
        persona=persona,
        session_id=session_id,
        language=language,
    )
    logger.info("voice_chat_text: chat done in %.2fs", time.monotonic() - t1)

    return JSONResponse(
        content={
            "session_id": str(session.get("id", "")),
            "turn_id": str(turn.get("id", "")),
            "transcript": transcript.strip(),
            "reply": reply_text,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/chat", response_model=None)
async def voice_chat(
    request: Request,
    audio: UploadFile = File(...),
    persona: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    output: Literal["json", "audio"] = Query(default="json"),
) -> JSONResponse | StreamingResponse:
    """Audio -> STT -> chat -> TTS. Returns JSON (with audio base64) or raw audio."""
    t0 = time.monotonic()
    audio_bytes = await _read_and_validate_audio(audio)
    transcript = await _transcribe_for_chat(audio_bytes, audio, language)
    logger.info("voice_chat: STT done in %.2fs", time.monotonic() - t0)

    session, turn, reply_text = await _chat_reply(
        transcript,
        persona=persona,
        session_id=session_id,
        language=language,
    )
    logger.info("voice_chat: chat done, reply_len=%d", len(reply_text))

    t2 = time.monotonic()
    try:
        audio_out, content_type = await synthesize_speech(reply_text)
        logger.info("voice_chat: TTS done in %.2fs, audio=%d bytes", time.monotonic() - t2, len(audio_out))
    except VoiceProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info("voice_chat: total %.2fs", time.monotonic() - t0)

    if output == "audio":
        return StreamingResponse(
            io.BytesIO(audio_out),
            media_type=content_type,
            headers={
                "X-Session-Id": str(session.get("id", "")),
                "X-Turn-Id": str(turn.get("id", "")),
                "X-Transcript": base64.b64encode(transcript.strip().encode("utf-8")).decode("ascii"),
                "X-Reply": base64.b64encode(reply_text.encode("utf-8")).decode("ascii"),
                "Cache-Control": "no-store",
            },
        )

    return JSONResponse(
        content={
            "session_id": str(session.get("id", "")),
            "turn_id": str(turn.get("id", "")),
            "transcript": transcript.strip(),
            "reply": reply_text,
            "audio_base64": base64.b64encode(audio_out).decode("ascii"),
            "audio_content_type": content_type,
        },
        headers={"Cache-Control": "no-store"},
    )
