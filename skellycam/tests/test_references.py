"""Check required provenance fields and source keys used by native audio."""
from pathlib import Path
import re


def test_native_audio_references_have_required_metadata():
    root = Path(__file__).resolve().parents[2]
    text = (root / "references.bib").read_text(encoding="utf-8")
    entries = dict(re.findall(r"@\w+\{(\w+),\s*(.*?)(?=\n\}|\Z)", text, re.S))
    sources = ["skellycam-rust/src/recording/audio.rs", "skellycam-rust/src/recording/recorder.rs",
               "skellycam/core/camera_group/rust_camera_group.py", "skellycam-rust/pyproject.toml",
               "RUST-BACKEND-DEVELOPMENT.md",
               "skellycam/core/camera/opencv/opencv_helpers/opencv_apply_config.py"]
    keys = [key for source in sources
            for key in re.findall(r"\[@(\w+)\]", (root / source).read_text(encoding="utf-8"))]
    assert keys
    for key in keys:
        assert key in entries
        for field in ("title", "url", "urldate", "review", "claim"):
            assert re.search(rf"\b{field}\s*=\s*\{{[^}}]+\}}", entries[key])
