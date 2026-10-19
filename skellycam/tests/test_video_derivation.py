from pathlib import Path

import numpy as np
import pytest

from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellycam.core.recorders.videos.video_derivation import VideoDerivation


@pytest.mark.parametrize("extension", ["mp4", "avi", "mov", "mkv"])
def test_source_relationship_survives_encoding(tmp_path: Path, extension: str) -> None:
    path = tmp_path / f"unrelated filename.{extension}"
    relationship = VideoDerivation(source_video="synchronized_videos/original.avi", frame_count=2)
    writer = PyavVideoWriter(path=str(path), fps=30.0, width=64, height=48)
    try:
        writer.set_container_metadata(metadata=relationship.to_container_metadata())
        for _ in range(2):
            writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    finally:
        writer.release()
    assert VideoDerivation.from_video(path=path) == relationship
