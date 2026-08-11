"""Audio service wrapper (Piece 6B).

Uses the shared TTS module in /audio (Chatterbox dev / Kokoro / ElevenLabs).
If TTS is unavailable (no provider configured, no voice sample, install
missing) it fails gracefully and returns a null audio path so the game still
runs - the frontend simply skips playback.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("audio_service")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import audio  # noqa: E402  (repo-root package)

    AUDIO_AVAILABLE = True
except Exception as e:  # pragma: no cover
    AUDIO_AVAILABLE = False
    logger.warning("Audio module unavailable: %s", e)
    audio = None  # type: ignore


def _cached_filename(character_id: str, text: str, ext: str) -> str:
    cid = character_id.lower()
    text_hash = hashlib.md5(f"{cid}:{text}".encode()).hexdigest()[:12]
    return f"{cid}_{text_hash}.{ext}"


def generate_voice(character_id: str, dialogue: str) -> dict:
    """TTS for one character line.

    Returns {"character_id", "audio_path", "duration", "available"}.
    audio_path is null when TTS is not available.
    """
    if not AUDIO_AVAILABLE or audio is None or not dialogue.strip():
        return _null_result(character_id, "audio module unavailable or empty dialogue")

    try:
        data, content_type = audio.generate_audio(dialogue, character_id)
        ext = "wav" if content_type == "audio/wav" else "mp3"
        filename = _cached_filename(character_id, dialogue, ext)
        cache_file = Path(audio.AUDIO_CACHE_DIR) / filename

        duration = _duration_of(cache_file)
        return {
            "character_id": character_id,
            "audio_path": f"/static/audio/{filename}",
            "duration": duration,
            "available": True,
        }
    except Exception as e:
        logger.exception("TTS failed for %s", character_id)
        return _null_result(character_id, str(e))


def _duration_of(wav_path: Path) -> float:
    try:
        import soundfile as sf

        info = sf.info(str(wav_path))
        return round(info.duration, 2)
    except Exception:
        return 0.0


def _null_result(character_id: str, reason: str) -> dict:
    logger.info("TTS skipped for %s: %s", character_id, reason)
    return {
        "character_id": character_id,
        "audio_path": None,
        "duration": 0.0,
        "available": False,
    }
