import hashlib
import logging
import platform

import cv2
from cv2.videoio_registry import getBackendName
from cv2_enumerate_cameras import supported_backends, enumerate_cameras
from cv2_enumerate_cameras.camera_info import CameraInfo
from pydantic import BaseModel, Field, computed_field
from tabulate import tabulate

from skellycam.core.camera.determine_backend import determine_opencv_camera_backend, OpenCVBackend
from skellycam.core.types.type_overloads import CameraIndexInt, CameraNameString, CameraBackendInt, CameraVendorIdInt, \
    CameraProductIdInt, CameraDevicePathString, CameraBackendNameString, CameraIdString

logger = logging.getLogger(__name__)

# define a function to search for a camera
def find_camera(
        index: CameraIndexInt | None = None,
        vid: CameraVendorIdInt | None = None,
        pid: CameraProductIdInt | None = None,
        path: CameraDevicePathString | None = None,
        api_preference: CameraBackendInt = cv2.CAP_ANY):
    for i in enumerate_cameras(api_preference):
        if index is not None and i.index == index:
            return cv2.VideoCapture(i.index, i.backend)
        if path is not None and i.path == path:
            return cv2.VideoCapture(i.index, i.backend)
        if vid is not None and pid is not None and i.vid == vid and i.pid == pid:
            return cv2.VideoCapture(i.index, i.backend)
    return None


class CaptureMode(BaseModel):
    """One MJPEG capture resolution and every frame rate the camera reports for it."""
    width: int
    height: int
    framerates: list[float]


class CameraDeviceInfo(BaseModel):
    index: CameraIndexInt
    name: CameraNameString
    vendor_id: CameraVendorIdInt | None = None
    product_id: CameraProductIdInt | None = None
    path: CameraDevicePathString | None = None
    backend_id: CameraBackendInt | None = None
    backend_name: CameraBackendNameString | None = None
    supported_modes: list[CaptureMode] = Field(
        default_factory=list,
        description="MJPEG capture modes from native detection, largest resolution first. "
                    "Empty when no natively detected device has this device's path.",
    )

    @computed_field
    @property
    def camera_id(self) -> CameraIdString:
        if self.path:
            raw = self.path
        elif self.vendor_id is not None and self.product_id is not None:
            raw = f"{self.vendor_id:04x}_{self.product_id:04x}_{self.index}"
        else:
            return format(self.index, '04x')
        digest = hashlib.sha256(raw.encode()).digest()
        return format(int.from_bytes(digest[:2], 'big'), '04x')

    @classmethod
    def from_camera_info(cls, camera_info: CameraInfo) -> 'CameraDeviceInfo':
        return cls(
            index=camera_info.index,
            name=camera_info.name,
            vendor_id=camera_info.vid,
            product_id=camera_info.pid,
            path=camera_info.path,
            backend_id=camera_info.backend,
            backend_name=getBackendName(camera_info.backend)
        )
    def create_cv2_video_capture(self) -> 'cv2.VideoCapture':
        cap = find_camera(
            vid=self.vendor_id,
            pid=self.product_id,
            path=self.path,
            api_preference=self.backend_id if self.backend_id is not None else cv2.CAP_ANY
        )
        if cap is None:
            raise RuntimeError(f"No matching camera found for index={self.index}, Vendor ID={self.vendor_id}, Product ID={self.product_id}")
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open camera {self.index} with Vendor ID: {self.vendor_id} and Product ID: {self.product_id}")
        # Attempt to read a frame to ensure the camera is working
        success, image = cap.read()

        if not success or image is None:
            cap.release()
            raise RuntimeError(f"Failed to read frame from camera {self.index} with Vendor ID: {self.vendor_id} and Product ID: {self.product_id}")
        return cap


def _detect_native_cameras() -> list[dict]:
    """Return the native engine's openpnp-capture detections, or none when it is unavailable."""
    try:
        import _skellycam_rust
        return _skellycam_rust.detect_cameras()
    except (ImportError, RuntimeError) as error:
        logger.warning(f"Camera capture modes unavailable: {type(error).__name__} - {error}")
        return []


def _capture_modes_for_path(path: CameraDevicePathString | None, native_detections: list[dict]) -> list[CaptureMode]:
    """Group the MJPEG formats of the native detection whose device is `path`.

    openpnp-capture identifies a device as "<name> <platform id>" [@openpnpCaptureDeviceIds].
    That id is the DirectShow DevicePath on Windows, which OpenCV's DirectShow enumeration
    reports as `path`, and the AVFoundation uniqueID on macOS [@cv2EnumerateCamerasPaths].
    Media Foundation links and Linux /dev/video* paths match no native device.
    """
    if not path:
        return []
    detection = next((native for native in native_detections if native["device_path"].endswith(f" {path}")), None)
    if detection is None:
        return []
    framerates: dict[tuple[int, int], set[int]] = {}
    for capture_format in detection["formats"]:
        if capture_format["fourcc_str"] == "MJPG":
            resolution = (capture_format["width"], capture_format["height"])
            framerates.setdefault(resolution, set()).add(capture_format["fps"])
    resolutions = sorted(framerates, key=lambda resolution: (resolution[0] * resolution[1], resolution[0]), reverse=True)
    return [CaptureMode(width=width, height=height, framerates=sorted(framerates[width, height]))
            for width, height in resolutions]


def detect_available_cameras(backend_id: CameraBackendInt|None=None, filter_virtual:bool=True) -> list[CameraDeviceInfo]:
    """
    Detects available cameras using the cv2_enumerate_cameras package.
    Returns a list of CameraInfo objects for each detected camera.
    """
    if backend_id is None:
        backend = determine_opencv_camera_backend()
    else:
        backend = OpenCVBackend.from_backend_id(backend_id)


    cameras: list[CameraDeviceInfo] =  []
    for camera_info in enumerate_cameras(apiPreference=backend.id):
        device = CameraDeviceInfo.from_camera_info(camera_info)
        if filter_virtual and 'virtual' in camera_info.name.lower():
            continue
        if 'darwin' not in platform.system().lower():
            # On Windows/Linux, VID/PID is reliably provided - skip cameras without it.
            # On macOS (AVFoundation), VID/PID are often unavailable even for real USB cameras.
            if camera_info.vid is None or camera_info.pid is None:
                continue
        if any(camera.camera_id == device.camera_id for camera in cameras):
            raise ValueError(f"Detected devices have colliding camera IDs: {device.camera_id}. Device paths: {[camera.path for camera in cameras]} and {device.path}")
        cameras.append(device)
    native_detections = _detect_native_cameras()
    for camera in cameras:
        camera.supported_modes = _capture_modes_for_path(camera.path, native_detections)
    logger.debug(f"Detected {len(cameras)} cameras:\n {tabulate([camera.model_dump() for camera in cameras], headers='keys')}\n)")
    return cameras

if __name__ == "__main__":
    print(f"Platform: {platform.system()}")
    print(f"OpenCV Version: {cv2.__version__}")
    print(f"Supported Backends: {[getBackendName(b) for b in supported_backends]}")
    _cameras = detect_available_cameras()
    if not _cameras:
        print("No _cameras detected.")
    else:
        for cam in _cameras:
            print(f"Camera Index: {cam.index}, Name: {cam.name}, Vendor ID: {cam.vendor_id}, Product ID: {cam.product_id}, Path: {cam.path}, Backend: {cam.backend_name} ({cam.backend_id})")
