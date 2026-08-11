# /home/jaidev/work/book-to-game/backend/audio/__init__.py
"""Audio module — TTS generation for game characters."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from audio.providers import (
    get_tts_provider, APP_DEV, TTS_PROVIDER,
    ChatterboxProvider, KokoroProvider,
)
from audio.voices import (
    get_chatterbox_sample, get_elevenlabs_voice_id, get_kokoro_voice_id,
)

audio_logger = logging.getLogger("audio")

AUDIO_CACHE_DIR = Path(__file__).resolve().parents[1] / "logs" / "audio"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _is_local_provider() -> bool:
    """Return True if the active provider runs locally (Chatterbox or Kokoro)."""
    return TTS_PROVIDER in ("chatterbox", "kokoro") or (
        TTS_PROVIDER == "" and APP_DEV.lower() == "dev"
    )


def get_audio_media_type() -> str:
    """Return the correct media type for the active provider."""
    return "audio/wav" if _is_local_provider() else "audio/mpeg"


def generate_audio(text: str, character_id: str) -> tuple[bytes, str]:
    """Generate speech audio for a character's line.

    Returns ``(audio_bytes, content_type)`` where content_type is
    ``"audio/wav"`` for local providers or ``"audio/mpeg"`` for ElevenLabs.
    """
    provider = get_tts_provider()
    cid = character_id.lower()
    ext = "wav" if _is_local_provider() else "mp3"
    content_type = "audio/wav" if ext == "wav" else "audio/mpeg"

    # Cache key based on text + character
    text_hash = hashlib.md5(f"{cid}:{text}".encode()).hexdigest()[:12]
    cache_file = AUDIO_CACHE_DIR / f"{cid}_{text_hash}.{ext}"

    # Return cached file if it exists and is valid
    if cache_file.exists() and cache_file.stat().st_size > 100:
        audio_logger.info("TTS CACHE HIT %s", cache_file.name)
        return cache_file.read_bytes(), content_type

    t0 = time.time()
    try:
        if isinstance(provider, ChatterboxProvider):
            sample = get_chatterbox_sample(cid)
            if not sample:
                raise ValueError(
                    f"No Chatterbox voice sample for '{cid}'. "
                    f"Add a .wav file to backend/voices/{cid}.wav"
                )
            audio_logger.info("TTS [chatterbox] character=%s text=%s", cid, text[:100])
            data = provider.generate(text, sample)

        elif isinstance(provider, KokoroProvider):
            voice_id = get_kokoro_voice_id(cid)
            if not voice_id:
                raise ValueError(
                    f"No Kokoro voice ID for '{cid}'. "
                    f"Add an entry to KOKORO_VOICE_IDS in backend/audio/voices.py"
                )
            audio_logger.info("TTS [kokoro] character=%s voice=%s text=%s", cid, voice_id, text[:100])
            data = provider.generate(text, voice_id)

        else:
            voice_id = get_elevenlabs_voice_id(cid)
            if not voice_id:
                raise ValueError(
                    f"No ElevenLabs voice ID for '{cid}'. "
                    f"Set ELEVENLABS_VOICE_IDS env var. Current value: {repr(getattr(provider, '_voice_ids_raw', ''))}"
                )
            audio_logger.info("TTS [elevenlabs] character=%s voice_id=%s text=%s", cid, voice_id, text[:100])
            data = provider.generate(text, voice_id)
    except Exception as e:
        audio_logger.exception("TTS FAILED character=%s error=%s", cid, e)
        raise

    elapsed = time.time() - t0

    # Save to disk for debugging
    cache_file.write_bytes(data)
    audio_logger.info(
        "TTS DONE character=%s size=%d bytes time=%.2fs saved=%s",
        cid, len(data), elapsed, cache_file.name,
    )

    return data, content_type


def generate_audio_stream(text: str, character_id: str):
    """Yields audio chunks from the active TTS provider."""
    provider = get_tts_provider()

    if isinstance(provider, ChatterboxProvider):
        voice_ref = get_chatterbox_sample(character_id)
        if not voice_ref:
            raise ValueError(
                f"No Chatterbox .wav sample for '{character_id}'. "
                f"Add backend/voices/{character_id}.wav"
            )
        return provider.generate_stream(text, voice_ref)

    elif isinstance(provider, KokoroProvider):
        voice_id = get_kokoro_voice_id(character_id)
        if not voice_id:
            raise ValueError(
                f"No Kokoro voice ID for '{character_id}'. "
                f"Add an entry to KOKORO_VOICE_IDS in backend/audio/voices.py"
            )
        return provider.generate_stream(text, voice_id)

    else:
        voice_id = get_elevenlabs_voice_id(character_id)
        if not voice_id:
            raise ValueError(f"No ElevenLabs voice ID for '{character_id}'")
        return provider.generate_stream(text, voice_id)
