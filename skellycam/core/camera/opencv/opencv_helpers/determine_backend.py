import logging
from platform import platform

import cv2
from cv2.videoio_registry import getBackendName
from cv2_enumerate_cameras import supported_backends
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OpenCVBackend(BaseModel):
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
    else:
        backend = OpenCVBackend.from_backend_id(supported_backends[0] if len(supported_backends) > 0 else cv2.CAP_ANY)
    logger.debug(f"Determined OpenCV backend: {backend.name} (ID: {backend.id})")
    return backend


if __name__ == "__main__":
    b = determine_opencv_camera_backend()
    print(f"OpenCV Backend: {b.name} (ID: {b.id})")