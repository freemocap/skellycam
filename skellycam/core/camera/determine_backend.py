import logging
import sys
from dataclasses import dataclass
from platform import platform

import cv2
from cv2.videoio_registry import getBackendName
from cv2_enumerate_cameras import supported_backends

logger = logging.getLogger(__name__)


@dataclass
class OpenCVBackend:
    id: int
    name: str

    @classmethod
    def from_backend_id(cls, backend_id: int) -> 'OpenCVBackend':
        name = getBackendName(backend_id)
        if name is None:
            logger.warning(f"Unknown OpenCV backend ID: {backend_id}. Defaulting to cv2.CAP_ANY.")
            backend_id = cv2.CAP_ANY
            name = getBackendName(backend_id)
        return cls(id=backend_id, name=name)


def determine_opencv_camera_backend() -> OpenCVBackend:
    if "windows" in platform().lower():
        # DSHOW (DirectShow) is the right choice for low-latency multi-camera capture on Windows.
        #
        # MSMF (Media Foundation) is the "modern" default on Windows 10+, but it adds a decode
        # transform pipeline with internal buffering that increases latency by 5-10ms and makes
        # grab/retrieve timing less predictable. MSMF also ignores CAP_PROP_BUFFERSIZE, so we
        # can't minimize stale-frame latency.
        #
        # DSHOW gives us:
        #   - Lower and more consistent grab-to-retrieve latency
        #   - Functional CAP_PROP_BUFFERSIZE control (we set it to 1 to avoid stale frames)
        #   - More direct access to the driver's sample delivery
        #   - Better multi-camera synchronization because frame delivery timing is more predictable
        backend = OpenCVBackend.from_backend_id(cv2.CAP_DSHOW)
    elif sys.platform == "linux":
        # V4L2 (Video4Linux2) is the native camera API on Linux.
        #
        # GStreamer may appear in cv2_enumerate_cameras.supported_backends (and may even be
        # the only entry), but opening a camera via cv2.VideoCapture(index, CAP_GSTREAMER)
        # with a plain integer index fails because GStreamer expects a pipeline string
        # (e.g. "v4l2src device=/dev/video0 ! ..."), not a numeric device index.
        #
        # V4L2 works correctly with integer device indices and provides direct, low-latency
        # access to the kernel's camera driver — analogous to DSHOW on Windows.
        #
        # We use CAP_V4L2 unconditionally here because cv2_enumerate_cameras.supported_backends
        # reflects enumeration support, not capture support. V4L2 is always available on Linux
        # when /dev/video* devices exist, even if cv2_enumerate_cameras doesn't list it.
        backend = OpenCVBackend.from_backend_id(cv2.CAP_V4L2)
    else:
        # macOS / other — use the first available backend, or CAP_ANY as fallback.
        # TODO: Check that this works on intel macs as well
        if cv2.CAP_AVFOUNDATION in supported_backends:
            logger.debug("AVFoundation backend is supported. Using AVFoundation for camera capture on macOS.")
            backend = OpenCVBackend.from_backend_id(cv2.CAP_AVFOUNDATION)
        else:
            logger.warning("AVFoundation backend is not supported. Defaulting to first available backend reported")
            backend = OpenCVBackend.from_backend_id(
                supported_backends[0] if len(supported_backends) > 0 else cv2.CAP_ANY
            )
    logger.debug(f"Determined OpenCV backend: {backend.name} (ID: {backend.id})")
    return backend


if __name__ == "__main__":
    b = determine_opencv_camera_backend()
    print(f"OpenCV Backend: {b.name} (ID: {b.id})")