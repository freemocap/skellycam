import logging
from http.client import HTTPResponse

from fastapi import APIRouter, Body, BackgroundTasks
from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.skellycam_app.skellycam_app_state import get_skellycam_app_state

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()



class CameraConnectRequest(BaseModel):
    camera_configs:CameraConfigs

    @classmethod
    def example(cls):
        return cls(camera_configs={0: CameraConfig(camera_id=0)})



@connect_cameras_router.post(
    "/cameras/connect",
    summary="Connect/Update specified cameras and apply provided configuration settings",
    tags=['Cameras']
)
def cameras_connect_post_endpoint(
        background_tasks: BackgroundTasks,
        request: CameraConnectRequest = Body(..., description="Request body containing camera IDs to connect",
                                             examples=[CameraConnectRequest.example()]),
):
    logger.api("Received `cameras/connect` POST request...")
    if not request.camera_configs:
        logger.error("No cameras provided in the request body.")
        return {"error": "No cameras provided."}
    try:
        configs = {CameraId(camera_id): config for camera_id, config in request.camera_configs.items()}
        background_tasks.add_task(get_skellycam_app_state().create_camera_group, camera_configs=configs)
        logger.api("`skellycam/connect` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)

def handle_connect_request(self, camera_configs: dict[CameraId, CameraConfig]):
    logger.debug("Handling cameras/connect request...")
    app_state = get_skellycam_app_state()
    if app_state.camera_group:
        logger.debug("Updating existing camera group with new camera configurations...")
        app_state.camera_group.update_camera_configs(camera_configs)
    else:
        logger.debug("Creating new camera group with provided camera configurations...")
        app_state.create_camera_group(camera_configs=camera_configs)

