"""Batch metadata probing owns file inspection and capture lifetime."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import MagicMock, patch

import cv2

from skellycam.core.recorders.videos.video_file_metadata import probe_video_files


class VideoMetadataTests(TestCase):
    def test_batch_probes_duplicate_path_once_and_releases_capture(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "arbitrary recording name.mp4"
            path.touch()
            capture = MagicMock()
            capture.isOpened.return_value = True
            values: dict[int, float] = {cv2.CAP_PROP_FRAME_WIDTH: 640.0, cv2.CAP_PROP_FRAME_HEIGHT: 480.0,
                cv2.CAP_PROP_FPS: 33.145, cv2.CAP_PROP_FRAME_COUNT: 48.0, cv2.CAP_PROP_FOURCC: 0.0}
            capture.get.side_effect = values.__getitem__
            with patch("skellycam.core.recorders.videos.video_file_metadata.cv2.VideoCapture", return_value=capture) as factory:
                metadata = probe_video_files(paths=[path, path])
                self.assertEqual(len(metadata), 1)
                factory.assert_called_once()
                capture.release.assert_called_once()

    def test_failed_open_releases_capture_and_raises(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "broken.mp4"
            path.touch()
            capture = MagicMock()
            capture.isOpened.return_value = False
            with patch("skellycam.core.recorders.videos.video_file_metadata.cv2.VideoCapture", return_value=capture):
                with self.assertRaisesRegex(ValueError, "Cannot open video"):
                    probe_video_files(paths=[path])
                capture.release.assert_called_once()


if __name__ == "__main__":
    main()
