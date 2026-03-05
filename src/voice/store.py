"""Voice profile persistence — JSON-backed load/save."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from distill.voice.models import VoiceProfile

logger = logging.getLogger(__name__)

VOICE_FILENAME = ".distill-voice.json"


def load_voice_profile(output_dir: Path) -> VoiceProfile:
    """Load voice profile from disk, or return empty profile."""
    path = output_dir / VOICE_FILENAME
    if not path.exists():
        return VoiceProfile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VoiceProfile.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt voice profile at %s, starting fresh", path)
        return VoiceProfile()


def save_voice_profile(profile: VoiceProfile, output_dir: Path) -> None:
    """Save voice profile to disk."""
    path = output_dir / VOICE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
