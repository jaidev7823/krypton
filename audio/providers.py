# /home/jaidev/work/book-to-game/backend/audio/providers.py
"""TTS provider implementations — Chatterbox (dev), Kokoro, and ElevenLabs (prod)."""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

APP_DEV = os.environ.get("APP_DEV", "")
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "").lower()
audio_prov_logger = logging.getLogger("audio")


# ---------------------------------------------------------------------------
# Chatterbox provider (dev)
# ---------------------------------------------------------------------------

class ChatterboxProvider:
    """Uses chatterbox-tts with reference audio samples for voice cloning."""

    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is None:
            import torch
            from chatterbox.tts import ChatterboxTTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = ChatterboxTTS.from_pretrained(device=device)
            self._patch_s3_dtype()

    def _patch_s3_dtype(self):
        """Monkeypatch S3 tokenizer to force float32 audio input."""
        import torch

        tok = None
        if hasattr(self._model, "s3gen") and hasattr(self._model.s3gen, "tokenizer"):
            tok = self._model.s3gen.tokenizer
        elif hasattr(self._model, "s3_tokenizer"):
            tok = self._model.s3_tokenizer

        if tok is None or not hasattr(tok, "log_mel_spectrogram"):
            return

        _orig = tok.log_mel_spectrogram

        def _patched(audio, padding=0):
            if not torch.is_tensor(audio):
                audio = torch.from_numpy(audio)
            return _orig(audio.float(), padding)

        tok.log_mel_spectrogram = _patched
        audio_prov_logger.info("Patched S3 tokenizer → float32")

    def generate(self, text: str, voice_ref_path: str) -> bytes:
        """Generate speech from text using a reference audio sample.

        Returns WAV bytes.
        """
        import soundfile as sf
        import torch

        self._load_model()
        audio_prov_logger.info("Chatterbox generate: text=%s ref=%s", text[:80], voice_ref_path)
        with torch.inference_mode():
            wav = self._model.generate(text, audio_prompt_path=voice_ref_path)

        if hasattr(wav, "detach"):
            wav = wav.detach().cpu().numpy()
        if wav.ndim == 2 and wav.shape[0] == 1:
            wav = wav.squeeze(0)

        buf = io.BytesIO()
        sf.write(buf, wav, self._model.sr, format="WAV")
        data = buf.getvalue()
        audio_prov_logger.info("Chatterbox done: %d bytes", len(data))
        return data

    def generate_stream(self, text: str, voice_ref_path: str):
        """Yield WAV audio bytes (single chunk for local model)."""
        data = self.generate(text, voice_ref_path)
        yield data

# ---------------------------------------------------------------------------
# Kokoro provider (local or remote via Kokoro-FastAPI)
# ---------------------------------------------------------------------------

class KokoroProvider:
    """Uses Kokoro-FastAPI (OpenAI-compatible endpoint) for text-to-speech.

    Requires a running Kokoro-FastAPI instance. Start one with Docker:

        docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu

    Or with GPU support:

        docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu

    Configure via env vars:
        KOKORO_API_BASE  — base URL (default http://localhost:8880/v1)
        KOKORO_API_KEY   — optional API key (default "not-needed")
    """

    def __init__(self):
        self._base_url = os.environ.get("KOKORO_API_BASE", "http://localhost:8880/v1")
        self._api_key = os.environ.get("KOKORO_API_KEY", "not-needed")

    def generate(self, text: str, voice_id: str) -> bytes:
        """Generate speech via Kokoro-FastAPI.

        Returns WAV bytes.
        """
        import requests

        url = f"{self._base_url}/audio/speech"
        payload = {
            "model": "kokoro",
            "input": text,
            "voice": voice_id,
            "response_format": "wav",
            "speed": 1.0,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        audio_prov_logger.info(
            "Kokoro generate: voice=%s text=%s url=%s",
            voice_id, text[:80], url,
        )
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()

        data = resp.content
        audio_prov_logger.info("Kokoro done: %d bytes", len(data))
        return data

    def generate_stream(self, text: str, voice_id: str):
        """Yield WAV audio bytes (single chunk — API returns complete file)."""
        data = self.generate(text, voice_id)
        yield data


# ---------------------------------------------------------------------------
# ElevenLabs provider (prod)
# ---------------------------------------------------------------------------

class ElevenLabsProvider:
    """Uses the ElevenLabs API for text-to-speech."""

    def __init__(self):
        from elevenlabs.client import ElevenLabs
        # Eager initialization warms up HTTP session / TLS handshake
        self._client = ElevenLabs()
        audio_prov_logger.info("ElevenLabs client initialized")

    def generate_stream(self, text: str, voice_id: str):
        """Yields audio chunks directly from ElevenLabs in real-time."""
        audio_prov_logger.info("ElevenLabs streaming: voice_id=%s text=%s", voice_id, text[:80])
        
        # client.text_to_speech.stream returns a generator yielding bytes
        return self._client.text_to_speech.stream(
            voice_id=voice_id,
            text=text,
            model_id="eleven_flash_v2_5",  # Fastest model (~100-200ms latency)
            optimize_streaming_latency=3,
            output_format="mp3_22050_32",
        )

    def generate(self, text: str, voice_id: str) -> bytes:
        """Fallback non-streaming sync method if full bytes are required."""
        stream = self.generate_stream(text, voice_id)
        chunks = [chunk for chunk in stream if isinstance(chunk, bytes)]
        return b"".join(chunks)

# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

_provider = None


def get_tts_provider():
    """Return the active TTS provider based on TTS_PROVIDER or APP_DEV env."""
    global _provider
    if _provider is None:
        if TTS_PROVIDER == "kokoro":
            _provider = KokoroProvider()
        elif TTS_PROVIDER == "elevenlabs":
            _provider = ElevenLabsProvider()
        elif TTS_PROVIDER == "chatterbox":
            _provider = ChatterboxProvider()
        elif APP_DEV.lower() == "dev":
            _provider = ChatterboxProvider()
        else:
            _provider = ElevenLabsProvider()
    return _provider
