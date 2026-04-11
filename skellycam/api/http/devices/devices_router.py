"""
Device discovery endpoints (read-only).

GET /devices/cameras
GET /devices/microphones
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from skellycam.core.device_detection.detect_cameras_devices import detect_available_cameras, CameraDeviceInfo
from skellycam.core.device_detection.detect_microphone_devices import get_available_microphones
from skellycam.core.types.type_overloads import CameraBackendInt

logger = logging.getLogger(__name__)

devices_router = APIRouter(prefix="/devices", tags=["Devices"])

class DetectedCamerasResponse(BaseModel):
    cameras: list[CameraDeviceInfo]


class DetectedMicrophonesResponse(BaseModel):
    microphones: dict[int, str]


@devices_router.get("/cameras", summary="Detect available camera devices")
def detect_cameras(
        filter_virtual: bool = True,
        backend_id: CameraBackendInt | None = None,
) -> DetectedCamerasResponse:
    try:
        cameras = detect_available_cameras(backend_id=backend_id, filter_virtual=filter_virtual)
        return DetectedCamerasResponse(cameras=cameras)
    except Exception as e:
        logger.error(f"Error detecting cameras: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@devices_router.get("/microphones", summary="Detect available microphone devices")
def detect_microphones() -> DetectedMicrophonesResponse:
    try:
        microphones = get_available_microphones()
        return DetectedMicrophonesResponse(microphones=microphones)
    except Exception as e:
        logger.error(f"Error detecting microphones: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
