import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_CAPACITY = 60  # ~2 seconds of buffering at 30fps, documented per-camera capacity
DEFAULT_SUBMIT_TIMEOUT_SECONDS = 0.5
DEFAULT_STOP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class StreamingFramePacket:
    frame_index: int
    camera_id: str
    timestamp_ns: int
    image: np.ndarray


@dataclass(frozen=True)
class StreamingWriterResult:
    success: bool
    frames_submitted: int
    frames_written: int
    peak_queue_depth: int
    output_path: Optional[Path]
    partial_path: Optional[Path]
    error: Optional[str] = None


class WriterSaturatedError(RuntimeError):
    """Raised when submit() cannot enqueue a frame within the allotted timeout.

    This is the bounded-queue backpressure contract: a short wait is allowed,
    but persistent saturation must fail loudly rather than silently drop
    synchronized frames.
    """


class WriterFailedError(RuntimeError):
    """Raised when submit() is called on a writer that has already failed."""


class FrameEncoder(Protocol):
    """Minimal interface a video encoder backend must satisfy. Lets tests
    substitute a fake/no-op encoder so memory-regression tests don't need to
    actually encode video."""

    def open(self, path: Path, width: int, height: int, fps: float) -> bool: ...

    def write(self, image: np.ndarray) -> None: ...

    def release(self) -> None: ...


class Cv2FrameEncoder:
    """Default production encoder backend -- thin wrapper over cv2.VideoWriter,
    matching the fourcc/container already used by the existing recorder."""

    def __init__(self, fourcc: str = "mp4v"):
        self._fourcc = fourcc
        self._writer = None

    def open(self, path: Path, width: int, height: int, fps: float) -> bool:
        import cv2

        self._writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*self._fourcc),
            fps,
            (int(width), int(height)),
        )
        return bool(self._writer.isOpened())

    def write(self, image: np.ndarray) -> None:
        self._writer.write(image)

    def release(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None


class StreamingVideoWriter:
    """Streams frames for a single camera to disk with bounded memory.

    Contrasts with the previous architecture (VideoRecorder.frame_payload_list):
    the encoder is opened at start(), a dedicated background thread drains a
    FINITE queue continuously during capture, and no frame image is retained
    once it has been written. Recording duration no longer determines RAM
    usage -- only queue_capacity does.
    """

    def __init__(
            self,
            output_path: Union[str, Path],
            expected_fps: float,
            queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
            submit_timeout_seconds: float = DEFAULT_SUBMIT_TIMEOUT_SECONDS,
            encoder: Optional[FrameEncoder] = None,
    ):
        self._final_path = Path(output_path)
        self._partial_path = self._final_path.with_name(
            self._final_path.stem + ".partial" + self._final_path.suffix
        )
        self._expected_fps = expected_fps
        self._queue_capacity = queue_capacity
        self._submit_timeout_seconds = submit_timeout_seconds
        self._encoder = encoder or Cv2FrameEncoder()

        self._queue: "queue.Queue[Optional[StreamingFramePacket]]" = queue.Queue(maxsize=queue_capacity)
        self._writer_thread: Optional[threading.Thread] = None
        self._timestamps: List[Tuple[int, int]] = []  # (frame_index, timestamp_ns) scalars only -- small
        self._lock = threading.Lock()

        self._started = False
        self._finished = False
        self._encoder_opened = False
        self._frames_submitted = 0
        self._frames_written = 0
        self._peak_queue_depth = 0
        self._failed = False
        self._error: Optional[str] = None

    # -- observable properties -------------------------------------------------
    @property
    def queue_capacity(self) -> int:
        return self._queue_capacity

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def frames_submitted(self) -> int:
        return self._frames_submitted

    @property
    def frames_written(self) -> int:
        return self._frames_written

    @property
    def peak_queue_depth(self) -> int:
        return self._peak_queue_depth

    @property
    def is_healthy(self) -> bool:
        return not self._failed

    @property
    def final_path(self) -> Path:
        return self._final_path

    @property
    def partial_path(self) -> Path:
        return self._partial_path

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self._started:
            raise RuntimeError("StreamingVideoWriter already started")
        self._partial_path.parent.mkdir(parents=True, exist_ok=True)
        self._started = True
        self._writer_thread = threading.Thread(
            target=self._drain_loop,
            name=f"StreamingVideoWriter-{self._final_path.name}",
            daemon=True,
        )
        self._writer_thread.start()

    def submit(self, packet: StreamingFramePacket, timeout_seconds: Optional[float] = None) -> None:
        """Enqueue one frame. Raises WriterSaturatedError if the bounded queue
        stays full past the timeout, and WriterFailedError if the writer has
        already failed -- callers must treat both as "abort this synchronized
        recording honestly," never as "drop this frame and continue."""
        if not self._started:
            raise RuntimeError("submit() called before start()")
        if self._failed:
            raise WriterFailedError(self._error or "writer previously failed")

        timeout = self._submit_timeout_seconds if timeout_seconds is None else timeout_seconds
        try:
            self._queue.put(packet, timeout=timeout)
        except queue.Full:
            self._failed = True
            self._error = f"writer queue saturated (capacity={self._queue_capacity})"
            raise WriterSaturatedError(self._error)

        with self._lock:
            self._frames_submitted += 1
            depth = self._queue.qsize()
            if depth > self._peak_queue_depth:
                self._peak_queue_depth = depth

    def stop(self, timeout_seconds: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> StreamingWriterResult:
        return self._finish(timeout_seconds=timeout_seconds, abort=False)

    def abort(self, reason: str, timeout_seconds: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> StreamingWriterResult:
        self._failed = True
        self._error = reason
        return self._finish(timeout_seconds=timeout_seconds, abort=True)

    # -- internal ----------------------------------------------------------
    def _finish(self, timeout_seconds: float, abort: bool) -> StreamingWriterResult:
        if self._finished:
            raise RuntimeError("StreamingVideoWriter.stop()/abort() already called")
        self._finished = True

        if not self._started:
            return StreamingWriterResult(
                success=False, frames_submitted=0, frames_written=0, peak_queue_depth=0,
                output_path=None, partial_path=None, error="writer was never started",
            )

        try:
            self._queue.put(None, timeout=timeout_seconds)  # sentinel: no more frames
        except queue.Full:
            self._failed = True
            self._error = self._error or "queue full while stopping"

        if self._writer_thread is not None:
            self._writer_thread.join(timeout=timeout_seconds)
            if self._writer_thread.is_alive():
                self._failed = True
                self._error = self._error or f"writer thread did not finish within {timeout_seconds}s"

        success = (
                not abort
                and not self._failed
                and self._frames_written > 0
                and self._frames_written == self._frames_submitted
        )

        if success:
            self._save_timestamps()
            self._final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(self._partial_path, self._final_path)  # atomic finalize
            return StreamingWriterResult(
                success=True,
                frames_submitted=self._frames_submitted,
                frames_written=self._frames_written,
                peak_queue_depth=self._peak_queue_depth,
                output_path=self._final_path,
                partial_path=None,
                error=None,
            )

        self._write_failure_metadata()
        return StreamingWriterResult(
            success=False,
            frames_submitted=self._frames_submitted,
            frames_written=self._frames_written,
            peak_queue_depth=self._peak_queue_depth,
            output_path=None,
            partial_path=self._partial_path if self._partial_path.exists() else None,
            error=self._error or "aborted",
        )

    def _drain_loop(self) -> None:
        try:
            while True:
                packet = self._queue.get()
                if packet is None:
                    break
                try:
                    if not self._encoder_opened:
                        opened = self._encoder.open(
                            path=self._partial_path,
                            width=packet.image.shape[1],
                            height=packet.image.shape[0],
                            fps=self._expected_fps,
                        )
                        if not opened:
                            self._failed = True
                            self._error = f"encoder failed to open for {self._partial_path}"
                            continue
                        self._encoder_opened = True

                    self._encoder.write(packet.image)
                    self._timestamps.append((packet.frame_index, packet.timestamp_ns))
                    self._frames_written += 1
                except Exception as exc:  # noqa: BLE001 -- must not crash the thread silently
                    logger.error(f"StreamingVideoWriter failed writing frame {packet.frame_index}: {exc}")
                    self._failed = True
                    self._error = str(exc)
                finally:
                    # Without this, `packet` (and its full-resolution image)
                    # stays alive in this stack frame for as long as the
                    # thread is blocked on the *next* queue.get() -- bounded
                    # (never grows), but not immediately GC-eligible either.
                    # Explicitly drop it so a written frame is freed the
                    # instant it's done, not "whenever the next one arrives."
                    packet = None
        finally:
            if self._encoder_opened:
                self._encoder.release()

    def _save_timestamps(self) -> None:
        """One-shot conversion of the small (frame_index, timestamp_ns) scalar
        list into the existing npy/csv format -- O(n) single allocation, not
        the previous np.append()-in-a-loop O(n^2) pattern. This list holds
        16 bytes/frame (two Python ints per tuple, negligible even for a long
        recording), never frame image data."""
        if not self._timestamps:
            return

        timestamp_folder = self._final_path.parent / "timestamps"
        timestamp_folder.mkdir(parents=True, exist_ok=True)
        base = timestamp_folder / self._final_path.stem

        timestamps_npy = np.array([ts for _, ts in self._timestamps], dtype=np.float64)

        npy_path = str(base) + "_binary.npy"
        np.save(npy_path, timestamps_npy)
        logger.info(f"Saved timestamps to path: {npy_path}")

        csv_path = str(base) + "_timestamps_human_readable.csv"
        pd.DataFrame(timestamps_npy).to_csv(csv_path)
        logger.info(f"Saved timestamps to path: {csv_path}")

    def _write_failure_metadata(self) -> None:
        if not self._partial_path.exists():
            return
        failure_path = self._partial_path.with_suffix(self._partial_path.suffix + ".failure.json")
        try:
            failure_path.write_text(json.dumps({
                "error": self._error,
                "frames_submitted": self._frames_submitted,
                "frames_written": self._frames_written,
                "peak_queue_depth": self._peak_queue_depth,
                "written_at_unix_time": time.time(),
            }, indent=2))
        except OSError as exc:
            logger.error(f"Could not write failure metadata for {self._partial_path}: {exc}")
