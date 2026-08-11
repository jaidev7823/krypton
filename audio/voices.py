# /home/jaidev/work/book-to-game/backend/audio/voices.py
"""Voice configuration — maps character IDs to TTS voice references."""

from __future__ import annotations

import os
from pathlib import Path

VOICES_DIR = Path(__file__).resolve().parents[1] / "voices"

# ElevenLabs voice IDs (character_id -> voice_id)
ELEVENLABS_VOICE_IDS: dict[str, str] = {
    "kessler": "EXAVITQu4vr4xnSDxMaL",   # Rachel
    "darnell": "N2lVS1w4EtoT3dr4eOWO",   # Domi
    "narration": "IKne3meq5aSn9XLyUdCD", # Sarah
    "marcus": "CwhRBWXzGAHq8TQ4Fs17",    # Antoni
    "uncle_ray": "pqHfZKP75CvOlQylNhV4"  # Josh
}
# Optional fallback narrator ID (hardcode string here if needed)
ELEVENLABS_NARRATOR_ID: str = "auq43ws1oslv0tO4BDa7"

# Kokoro voice IDs (character_id -> voice preset name)
# See https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
KOKORO_VOICE_IDS: dict[str, str] = {
    "kessler": "af_bella",      # Female, authoritative (A- grade)
    "darnell": "am_michael",    # Male, professional (C+ grade)
    "narration": "am_adam",     # Male, clear narration (B- grade)
    "marcus": "am_fenrir",      # Male, confident (C+ grade)
    "uncle_ray": "am_onyx",     # Male, warm (C+ grade)
    "halloran": "am_santa",     # Male, seasoned (well-tested default)
}


def get_chatterbox_sample(character_id: str) -> str | None:
    """Return the path to a Chatterbox reference .wav sample, or None."""
    sample = VOICES_DIR / f"{character_id.lower()}.wav"
    return str(sample) if sample.exists() else None


def get_elevenlabs_voice_id(character_id: str) -> str | None:
    """Return the ElevenLabs voice ID for a character, or None."""
    cid = character_id.lower()
    
    # Check exact match or mapped aliases (e.g., 'narrator' -> 'narration')
    if cid in ELEVENLABS_VOICE_IDS:
        return ELEVENLABS_VOICE_IDS[cid]
        
    if cid == "narrator":
        return ELEVENLABS_VOICE_IDS.get("narration", ELEVENLABS_NARRATOR_ID)
        
    return None


def get_kokoro_voice_id(character_id: str) -> str | None:
    """Return the Kokoro voice preset name for a character, or None."""
    cid = character_id.lower()

    if cid in KOKORO_VOICE_IDS:
        return KOKORO_VOICE_IDS[cid]

    if cid == "narrator":
        return KOKORO_VOICE_IDS.get("narration")

    return None