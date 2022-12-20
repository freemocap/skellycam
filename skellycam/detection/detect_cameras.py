from skellycam.detection.private.detect_possible_cameras import DetectPossibleCameras
from skellycam.detection.private.found_camera_cache import FoundCameraCache

# No consumer should call this "private" variable
_available_cameras: FoundCameraCache = None


# If you want cams, you call this function
def detect_cameras(use_cache=True):
    global _available_cameras
    if _available_cameras is None or not use_cache:
        d = DetectPossibleCameras()
        _available_cameras = d.find_available_cameras()

    return _available_cameras
