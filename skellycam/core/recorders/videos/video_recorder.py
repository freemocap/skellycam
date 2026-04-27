import logging
import os
import signal
import sys
import tempfile
import time
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig, FOURCC_TO_EXTENSION
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)

# Codecs to try (in order) when the requested codec is unavailable.
# Ordered to prefer MP4 containers across platforms before falling back to AVI:
#   X264/H264 — compact H.264 mp4. Bundled on Windows OpenCV; usually NOT on
#               pip-installed OpenCV for Linux/macOS (no libx264).
#   avc1      — H.264 via Apple VideoToolbox. Mac-native MP4 path.
#   mp4v      — MPEG-4 Part 2 in mp4. Less efficient than H.264 but very
#               widely available, including on macOS and Linux.
#   XVID      — AVI container. Widely available cross-platform.
#   MJPG      — Universally supported AVI fallback of last resort (large files).
_FALLBACK_CODECS = ["X264", "H264", "avc1", "mp4v", "XVID", "MJPG"]

_CODEC_PROBE_TIMEOUT_SECONDS = 5


class _CodecProbeTimeout(Exception):
    pass


def _probe_codec(fourcc_str: str, frame_size: tuple[int, int]) -> bool:
    """Return True if cv2.VideoWriter can write a frame with this codec.

    Uses a unique temp file per call to avoid race conditions when multiple
    camera worker processes probe codecs simultaneously.  Times out after
    _CODEC_PROBE_TIMEOUT_SECONDS to avoid hanging on broken codec backends.
    """
    logger.debug(f"Probing video codec '{fourcc_str}' with frame size {frame_size}...")
    ext = FOURCC_TO_EXTENSION.get(fourcc_str, "avi")
    fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", prefix="_skellycam_codec_probe_")
    os.close(fd)
    test_frame = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
    writer: cv2.VideoWriter | None = None

    def _timeout_handler(signum: int, frame: object) -> None:
        raise _CodecProbeTimeout(f"Codec probe for '{fourcc_str}' timed out after {_CODEC_PROBE_TIMEOUT_SECONDS}s")

    old_handler = None
    if sys.platform != "win32":
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(_CODEC_PROBE_TIMEOUT_SECONDS)

    try:
        writer = cv2.VideoWriter(
            tmp_path,
            cv2.VideoWriter.fourcc(*fourcc_str),
            30.0,
            frame_size,
        )
        if not writer.isOpened():
            logger.debug(f"Codec '{fourcc_str}' failed: writer did not open")
            return False
        writer.write(test_frame)
        writer.release()
        writer = None
        # Verify the file has actual content (some backends open but write nothing)
        ok = Path(tmp_path).stat().st_size >= 100
        logger.debug(f"Codec '{fourcc_str}' probe {'succeeded' if ok else 'failed (empty file)'}")
        return ok
    except _CodecProbeTimeout:
        logger.warning(f"Codec '{fourcc_str}' probe timed out — skipping")
        return False
    except Exception as e:
        logger.debug(f"Codec '{fourcc_str}' probe failed with {type(e).__name__}: {e}")
        return False
    finally:
        if sys.platform != "win32":
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        if writer is not None:
            writer.release()
        Path(tmp_path).unlink(missing_ok=True)


def resolve_writer_fourcc(requested_fourcc: str, frame_size: tuple[int, int]) -> str:
    """Return a working fourcc string, trying the requested one first then fallbacks.

    Raises RuntimeError if no codec works at all.
    """
    # Try the requested codec first
    if _probe_codec(fourcc_str=requested_fourcc, frame_size=frame_size):
        return requested_fourcc

    logger.warning(
        f"Requested video codec '{requested_fourcc}' is not available on this system. "
        f"Probing fallback codecs: {_FALLBACK_CODECS}"
    )

    for fourcc_str in _FALLBACK_CODECS:
        if fourcc_str == requested_fourcc:
            continue  # Already tried
        if _probe_codec(fourcc_str=fourcc_str, frame_size=frame_size):
            logger.info(f"Using fallback video codec: {fourcc_str}")
            return fourcc_str

    raise RuntimeError(
        f"No usable video writer codec found (tried '{requested_fourcc}' and {_FALLBACK_CODECS}). "
        f"Ensure OpenCV is built with FFMPEG support or install codec libraries."
    )


@dataclass
class VideoRecorder:
    camera_id: CameraIdString
    camera_index: int
    video_file_path: str
    video_image_shape: tuple[int, int]  # (width, height) as per OpenCV convention
    framerate: float
    writer_fourcc: str
    recording_info: RecordingInfo
    video_frame_metadata: list[np.recarray] = field(default_factory=list)
    previous_frame_number: int | None = None
    video_writer: cv2.VideoWriter | None = None

    @property
    def any_data_saved(self) -> bool:
        return self.previous_frame_number is not None

    @classmethod
    def create(
            cls,
            recording_info: RecordingInfo | None,
            config: CameraConfig,
            framerate: float | None = None,
    ) -> "VideoRecorder":
        if recording_info is None:
            recording_info = RecordingInfo.create_temp()

        video_image_shape: tuple[int, int]
        if config.rotation.value == -1 or config.rotation.value == cv2.ROTATE_180:
            video_image_shape = (config.resolution.width, config.resolution.height)
        else:
            video_image_shape = (config.resolution.height, config.resolution.width)

        # Resolve a codec that actually works on this platform
        working_fourcc = resolve_writer_fourcc(
            requested_fourcc=config.writer_fourcc,
            frame_size=video_image_shape,
        )

        # Build the video file path using the working codec's extension
        ext = FOURCC_TO_EXTENSION.get(working_fourcc, "avi")
        if not ext == config.video_file_extension:
            logger.warning(f"Resolved codec ({working_fourcc} and extension ({ext})) do not match config defined codec ({config.writer_fourcc} and {config.video_file_extension}) — using resolved codec and extension")

        video_file_path = recording_info.video_file_path_from_camera_config(config=config, extension=ext)
        Path(video_file_path).parent.mkdir(parents=True, exist_ok=True)

        logger.debug(
            f"Created VideoSaver for camera {config.camera_index} "
            f"with codec={working_fourcc}, path={video_file_path}"
        )
        instance = cls(
            camera_id=config.camera_id,
            camera_index=config.camera_index,
            video_file_path=video_file_path,
            video_image_shape=video_image_shape,
            framerate=config.framerate if framerate is None else framerate,
            writer_fourcc=working_fourcc,
            recording_info=recording_info,
        )
        instance._initialize_video_writer()
        return instance

    def record_frame(self, frame: np.recarray) -> np.ndarray:
        if not self.video_writer.isOpened():
            raise RuntimeError("VideoWriter not open (before adding frame)!")

        self._validate_frame_number(frame)
        if frame.frame_metadata.camera_info.rotation != -1:
            image = cv2.rotate(
                frame.image[0],
                frame.frame_metadata.camera_info.rotation[0],
            )
        else:
            image = frame.image[0]
        self._validate_image_shape(image)

        frame.frame_metadata.timestamps.pre_frame_record_ns[0] = time.perf_counter_ns()
        self.video_writer.write(image)
        frame.frame_metadata.timestamps.post_frame_record_ns[0] = time.perf_counter_ns()

        self.previous_frame_number = frame.frame_metadata.frame_number[0]
        if not self.video_writer.isOpened():
            raise RuntimeError("VideoWriter not open (after adding frame)!")
        self.video_frame_metadata.append(copy(frame.frame_metadata))
        return frame.frame_metadata.frame_number

    def finish_and_close(self) -> list[np.recarray]:
        logger.debug(f"Finishing and closing VideoSaver for camera {self.camera_id}")
        self.close()
        return self.video_frame_metadata

    def _initialize_video_writer(self) -> None:
        self.video_writer = cv2.VideoWriter(
            self.video_file_path,
            cv2.VideoWriter.fourcc(*self.writer_fourcc),
            self.framerate,
            self.video_image_shape,
        )
        if not self.video_writer.isOpened():
            raise RuntimeError(
                f"Failed to open video writer for camera {self.camera_index} "
                f"with codec={self.writer_fourcc}, path={self.video_file_path}"
            )
        logger.debug(
            f"Initialized VideoRecorder for camera {self.camera_index} "
            f"- Video file will be saved to {self.video_file_path}"
        )

    def _validate_image_shape(self, image: np.ndarray) -> None:
        image_video_shape = (image.shape[1], image.shape[0])
        if image_video_shape != self.video_image_shape:
            raise ValueError(
                f"Frame shape ({image_video_shape}) does not match "
                f"expected shape ({self.video_image_shape})"
            )

    def _validate_frame_number(self, frame: np.recarray) -> None:
        if self.previous_frame_number is not None:
            if frame.frame_metadata.frame_number[0] != self.previous_frame_number + 1:
                raise ValueError(
                    f"Frame numbers for camera {self.camera_id} are not consecutive! "
                    f"Previous: {self.previous_frame_number}, "
                    f"Current: {frame.frame_metadata.frame_number[0]}"
                )

    def close(self) -> None:
        if self.video_writer:
            self.video_writer.release()
            logger.info(
                f"Camera {self.camera_id} - Video file saved to {self.video_file_path}"
            )
