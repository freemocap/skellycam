import logging
import re

import sounddevice as sd

logger = logging.getLogger(__name__)

# Names that are virtual/system devices, not real microphones
_GARBAGE_PATTERNS: list[str] = [
    # Windows
    r"microsoft sound mapper",
    r"primary sound",
    r"default$",
    r"^mapear",            # Spanish "mapper"
    r"^zuordnung",         # German "mapper"
    r"^wave/in$",
    r"^rec\. playback",
    r"stereo mix",
    r"what u hear",
    r"loopback",
    # macOS
    r"^aggregate device$",
    r"^multi-output device$",
    r"^blackhole",
    r"^soundflower",
    r"^existential audio",
    # Linux (PulseAudio/PipeWire monitor sources)
    r"^monitor of ",
    r"^auto_null",
    r"^null ",
]

_GARBAGE_RE = re.compile("|".join(_GARBAGE_PATTERNS), re.IGNORECASE)


def get_available_microphones() -> dict[int, str]:
    """Detect available microphone input devices, deduplicating and filtering garbage.

    When multiple host APIs expose the same physical device (e.g. MME, WDM-KS,
    WASAPI), we keep only the first occurrence of each device name.
    Virtual/system devices like "Stereo Mix" or "Microsoft Sound Mapper" are excluded.
    """
    devices = sd.query_devices()
    seen_names: set[str] = set()
    microphones: dict[int, str] = {}

    for i, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue

        name: str = device["name"].strip()
        if not name:
            continue

        # Skip virtual/garbage devices
        if _GARBAGE_RE.search(name):
            continue

        # Deduplicate by normalized name (case-insensitive, whitespace-collapsed)
        normalized = re.sub(r"\s+", " ", name).lower()
        if normalized in seen_names:
            continue
        seen_names.add(normalized)

        microphones[i] = name

    return microphones


if __name__ == "__main__":
    from pprint import pprint
    pprint(get_available_microphones())
