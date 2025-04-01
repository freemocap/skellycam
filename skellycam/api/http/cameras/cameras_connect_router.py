import logging

from fastapi import APIRouter, Body
from pydantic import BaseModel

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, \
    default_camera_configs_factory
from skellycam.skellycam_app.skellycam_app import get_skellycam_app

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()



class CameraConnectRequest(BaseModel):
    camera_configs:CameraConfigs

    @classmethod
    def example(cls):
        return cls(camera_configs=default_camera_configs_factory())



@connect_cameras_router.post(
    "/cameras/connect",
    summary="Connect/Update specified cameras and apply provided configuration settings",
    tags=['Cameras']
)
def cameras_connect_post_endpoint(
        request: CameraConnectRequest = Body(..., description="Request body containing camera IDs to connect",
                                             examples=[CameraConnectRequest.example()]),
):
    logger.api("Received `cameras/connect` POST request...")
    if not request.camera_configs:
        logger.error("No cameras provided in the request body.")
        return {"error": "No cameras provided."}
    try:
        get_skellycam_app().create_or_update_camera_group(camera_configs=request.camera_configs)
        logger.api("`skellycam/connect` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)

