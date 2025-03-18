import logging
from http.client import HTTPResponse

from fastapi import APIRouter, Body, BackgroundTasks
from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.skellycam_app.skellycam_app_state import get_skellycam_app_state

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


class CameraConnectRequest(BaseModel):
    camera_ids: list[CameraId] = Body(default=[0], description="List of camera IDs to connect")

    @classmethod
    def example(cls):
        return {
            "camera_ids": [CameraId(0)]
        }


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
    logger.api("Received `skellycam/connect` POST request...")
    if not request.camera_ids:
        logger.error("No camera IDs provided in the request body.")
        return {"error": "No camera IDs provided."}
    try:
        camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in request.camera_ids}
        background_tasks.add_task(get_skellycam_app_state().create_camera_group, camera_configs=camera_configs)
        logger.api("`skellycam/connect` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)

# @connect_cameras_router.get(
#     "/connect",
#     summary="Detect and connect to all available cameras with default settings",
# )
# def cameras_connect_get_endpoint():
#     logger.api("Received `skellycam/connect` GET request...")
#     try:
#         get_skellycam_app_controller().connect_to_cameras()
#         logger.api("`skellycam/connect` GET request handled successfully.")
#     except Exception as e:
#         logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
#         logger.exception(e)
