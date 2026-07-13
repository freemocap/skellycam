import logging
import traceback
from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np
import pandas as pd

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.streaming_video_writer import (
    DEFAULT_QUEUE_CAPACITY,
    StreamingFramePacket,
    StreamingVideoWriter,
    StreamingWriterResult,
    WriterFailedError,
    WriterSaturatedError,
)

logger = logging.getLogger(__name__)

__all__ = [
    "VideoRecorder",
    "StreamingWriterResult",
    "WriterFailedError",
    "WriterSaturatedError",
]


class VideoRecorder:
    """Per-camera recording handle.

    Historically this class accumulated every captured frame in an unbounded
    `_frame_payload_list` for the entire recording, then wrote them all out
    (and was `deepcopy()`-ed in full, images included) at Stop. That is the
    root cause this class was rewritten to fix -- see ARCHITECTURE_REPORT.md.

    It now streams frames to disk via a bounded-queue `StreamingVideoWriter`,
    opened at `start_streaming()` (recording Start), fed one frame at a time
    by `append_frame_payload_to_list()` (kept under its historical name so
    existing call sites don't need to change), and finalized by
    `stop_streaming()` / `abort_streaming()` at Stop. No frame image is ever
    retained by this class once it has been submitted to the writer.
    """

    def __init__(self):
        self._streaming_writer: Optional[StreamingVideoWriter] = None
        self._path_to_save_video_file: Optional[Path] = None

    # -- new streaming lifecycle -------------------------------------------------
    @property
    def is_streaming(self) -> bool:
        return self._streaming_writer is not None

    @property
    def is_healthy(self) -> bool:
        return self._streaming_writer is None or self._streaming_writer.is_healthy

    def start_streaming(
            self,
            video_file_save_path: Union[str, Path],
            expected_fps: float,
            queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
    ) -> None:
        if self._streaming_writer is not None:
            raise RuntimeError("VideoRecorder already streaming -- call stop_streaming() first")

        self._path_to_save_video_file = Path(video_file_save_path)
        self._streaming_writer = StreamingVideoWriter(
            output_path=self._path_to_save_video_file,
            expected_fps=expected_fps,
            queue_capacity=queue_capacity,
        )
        self._streaming_writer.start()

    def stop_streaming(self, timeout_seconds: float = 10.0) -> StreamingWriterResult:
        if self._streaming_writer is None:
            raise RuntimeError("stop_streaming() called before start_streaming()")
        return self._streaming_writer.stop(timeout_seconds=timeout_seconds)

    def abort_streaming(self, reason: str, timeout_seconds: float = 10.0) -> StreamingWriterResult:
        if self._streaming_writer is None:
            raise RuntimeError("abort_streaming() called before start_streaming()")
        return self._streaming_writer.abort(reason=reason, timeout_seconds=timeout_seconds)

    @property
    def number_of_frames(self) -> int:
        """Frames *submitted* to the writer so far. Kept under its historical
        name/shape for compatibility with existing diagnostic call sites."""
        if self._streaming_writer is None:
            return 0
        return self._streaming_writer.frames_submitted

    @property
    def peak_queue_depth(self) -> int:
        if self._streaming_writer is None:
            return 0
        return self._streaming_writer.peak_queue_depth

    def append_frame_payload_to_list(self, frame_payload: FramePayload, frame_index: int) -> None:
        """Historical name, new behavior: submits directly to the bounded
        streaming queue instead of appending to an unbounded in-RAM list.

        Raises WriterSaturatedError / WriterFailedError -- callers (the
        capture loop) must treat either as grounds to abort the entire
        synchronized recording honestly, not to silently drop this frame.
        """
        if self._streaming_writer is None:
            raise RuntimeError("append_frame_payload_to_list() called before start_streaming()")

        packet = StreamingFramePacket(
            frame_index=frame_index,
            camera_id=str(frame_payload.camera_id),
            timestamp_ns=int(frame_payload.timestamp_ns),
            image=frame_payload.image,
        )
        self._streaming_writer.submit(packet)

    # -- legacy calibration-video path (unchanged) --------------------------
    # save_image_list_to_disk operates on an already-complete, caller-owned
    # image_list (e.g. a small set of calibration snapshots), not a live
    # growing camera recording -- it was never implicated in the unbounded-
    # memory bug and is left as-is.
    def save_image_list_to_disk(
            self,
            image_list: List[np.ndarray],
            path_to_save_video_file: Union[str, Path],
            frames_per_second: float,
    ):
        if len(image_list) == 0:
            logging.error(f"No frames to save for : {path_to_save_video_file}")
            return

        cv2_video_writer = self._initialize_video_writer(
            image_height=image_list[0].shape[0],
            image_width=image_list[0].shape[1],
            frames_per_second=frames_per_second,
            path_to_save_video_file=path_to_save_video_file,
        )
        try:
            for image in image_list:
                cv2_video_writer.write(image)
        except Exception as e:
            logger.error(f"Failed during save in video writer for video {str(path_to_save_video_file)}")
            traceback.print_exc()
            raise e
        finally:
            cv2_video_writer.release()

    def _initialize_video_writer(
            self,
            image_height: Union[int, float],
            image_width: Union[int, float],
            path_to_save_video_file: Union[str, Path],
            frames_per_second: Union[int, float] = None,
            fourcc: str = "mp4v",
    ) -> cv2.VideoWriter:
        video_writer_object = cv2.VideoWriter(
            str(path_to_save_video_file),
            cv2.VideoWriter_fourcc(*fourcc),
            frames_per_second,
            (int(image_width), int(image_height)),
        )

        if not video_writer_object.isOpened():
            logger.error(f"cv2.VideoWriter failed to initialize for: {str(path_to_save_video_file)}")
            raise Exception("cv2.VideoWriter is not open")

        return video_writer_object
