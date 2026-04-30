import numpy as np

class PyavVideoWriter:
    """cv2.VideoWriter-compatible wrapper that encodes H264 via pyav/libx264.

    Used on Linux when pip-installed OpenCV's bundled FFmpeg lacks libx264.
    Presents the same isOpened/write/release interface as cv2.VideoWriter so
    VideoRecorder can treat both paths identically.
    """

    def __init__(self, path: str, fps: float, width: int, height: int) -> None:
        import av  # noqa: TC002 — runtime import intentional (lazy, optional dep) - can cause issues on Mac if imported at top level
        self._container = av.open(path, mode='w')
        self._stream = self._container.add_stream('libx264', rate=int(round(fps)))
        self._stream.width = width
        self._stream.height = height
        self._stream.pix_fmt = 'yuv420p'
        self._stream.options = {'crf': '18', 'preset': 'fast'}
        self._frame_count = 0
        self._open = True

    def isOpened(self) -> bool:  # noqa: N802 — match cv2.VideoWriter API
        return self._open

    def write(self, frame: np.ndarray) -> None:
        import av  # noqa: TC002 — av is cached in sys.modules after __init__; this just binds the name
        av_frame = av.VideoFrame.from_ndarray(frame, format='bgr24')
        av_frame.pts = self._frame_count
        self._frame_count += 1
        for packet in self._stream.encode(av_frame):
            self._container.mux(packet)

    def release(self) -> None:
        if not self._open:
            return
        self._open = False
        for packet in self._stream.encode():
            self._container.mux(packet)
        self._container.close()

