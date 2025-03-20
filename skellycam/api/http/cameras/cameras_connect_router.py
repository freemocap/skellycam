import logging
from http.client import HTTPResponse

from fastapi import APIRouter, Body, BackgroundTasks
from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.skellycam_app.skellycam_app_state import get_skellycam_app_state

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()

class MediaDevice(BaseModel):
    # https://developer.mozilla.org/en-US/docs/Web/API/MediaDeviceInfo
    deviceId: str # camelCase to match the MediaDeviceInfo API
    groupId: str
    kind: str
    label: str

    @classmethod
    def example(cls):
        return cls(
            deviceId= "camera_0_abcd",
            groupId= "group_0_abcd",
            kind= "videoinput",
            label= "Camera 0"
        )

class CameraConnectRequest(BaseModel):
    camera_devices: list[MediaDevice] = Body(default=[MediaDevice.example()], description="List of camera devices to connect (JSON array of MediaDevice objects)")



@connect_cameras_router.post(
    "/cameras/connect",
    summary="Connect/Update specified cameras and apply provided configuration settings",
    tags=['Cameras']
)
def cameras_connect_post_endpoint(
        background_tasks: BackgroundTasks,
        request: CameraConnectRequest = Body(..., description="Request body containing camera IDs to connect",
                                             examples=[CameraConnectRequest()]),
):
    logger.api("Received `skellycam/connect` POST request...")
    if not request.camera_devices:
        logger.error("No camera IDs provided in the request body.")
        return {"error": "No camera IDs provided."}
    try:
        camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id, camera_device in enumerate(request.camera_devices)}
        background_tasks.add_task(get_skellycam_app_state().create_camera_group, camera_configs=camera_configs)
        logger.api("`skellycam/connect` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)

