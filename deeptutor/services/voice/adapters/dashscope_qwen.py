"""DashScope Qwen Audio ASR streaming adapter (Bailian)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile

import dashscope

from deeptutor.services.voice.audio import FFMPEG_STT_INSTALL_HINT
from deeptutor.services.voice.base import BaseSTTAdapter, VoiceProviderError
from deeptutor.services.voice.config import STTConfig


class DashScopeQwenASRAdapter(BaseSTTAdapter):
    """Transcribe audio using DashScope/Bailian Qwen Audio streaming ASR.

    This adapter uses the ``dashscope.Client.audio.asr.recognize_file`` API
    introduced for ``qwen-audio-*-asr-flash-streaming`` models.  It runs the
    synchronous SDK in a thread executor so the caller stays async.
    """

    _SUPPORTED_MODELS: frozenset[str] = frozenset(
        {
            "qwen-audio-3.1-asr-flash-streaming",
            "qwen-audio-3.0-asr-flash-streaming",
        }
    )

    async def transcribe(
        self,
        audio: bytes,
        config: STTConfig,
        *,
        filename: str = "audio.webm",
        content_type: str = "application/octet-stream",
    ) -> str:
        if not audio:
            raise VoiceProviderError("No audio data to transcribe.")
        if not config.api_key or config.api_key == "***":
            raise VoiceProviderError("Configure a DashScope API key for speech recognition.")
        if config.model not in self._SUPPORTED_MODELS:
            raise VoiceProviderError(
                f"Unsupported Qwen ASR model: {config.model}. "
                "Use qwen-audio-3.1-asr-flash-streaming or qwen-audio-3.0-asr-flash-streaming."
            )

        suffix = self._suffix_from_filename(filename, content_type)
        with tempfile.TemporaryDirectory(prefix="deeptutor-qwen-asr-") as directory:
            wav_path = await self._to_wav(audio, suffix, Path(directory))

            loop = asyncio.get_running_loop()
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self._recognize_file,
                        wav_path,
                        config,
                    ),
                    timeout=config.request_timeout,
                )
            except asyncio.TimeoutError as exc:
                raise VoiceProviderError(
                    "DashScope Qwen ASR timed out. Increase the request timeout in the STT settings."
                ) from exc
            except Exception as exc:
                if isinstance(exc, VoiceProviderError):
                    raise
                raise VoiceProviderError(f"DashScope Qwen ASR request failed: {exc}") from exc

    def _recognize_file(self, path: Path, config: STTConfig) -> str:
        client = dashscope.Client(api_key=config.api_key)
        events = client.audio.asr.recognize_file(
            str(path),
            model=config.model,
            format="wav",
            sample_rate=16000,
        )

        sentences: list[str] = []
        for event in events:
            payload = (event or {}).get("payload") or {}
            output = payload.get("output") or {}
            sentence = output.get("sentence") or {}
            text = sentence.get("text")
            if text and not sentence.get("heartbeat") and sentence.get("sentence_end"):
                sentences.append(str(text))

        return "".join(sentences).strip()

    def _suffix_from_filename(self, filename: str, content_type: str) -> str:
        suffix = Path(filename).suffix.lstrip(".").lower()
        if suffix in {"wav", "mp3", "pcm", "ogg", "opus", "flac", "m4a", "webm", "aac"}:
            return suffix
        media_type = (content_type or "").split(";", 1)[0].strip().lower()
        return {
            "audio/wav": "wav",
            "audio/mpeg": "mp3",
            "audio/aac": "aac",
            "audio/ogg": "ogg",
            "audio/opus": "opus",
            "audio/webm": "webm",
            "audio/mp4": "m4a",
            "audio/pcm": "pcm",
        }.get(media_type, "webm")

    async def _to_wav(self, audio: bytes, suffix: str, directory: Path) -> Path:
        source = directory / f"audio.{suffix}"
        target = directory / "audio.wav"
        source.write_bytes(audio)

        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(target),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise VoiceProviderError(
                "ffmpeg is required to normalize audio for DashScope Qwen ASR. "
                + FFMPEG_STT_INSTALL_HINT
            ) from exc

        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()[:400]
            raise VoiceProviderError(
                "Could not convert audio to WAV for DashScope Qwen ASR"
                + (f": {detail}" if detail else ".")
            )
        return target


__all__ = ["DashScopeQwenASRAdapter"]
