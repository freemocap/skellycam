import logging

from fastapi import APIRouter, Body

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, default_camera_configs_factory
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


# @connect_cameras_router.post(
#     "/connect",
#
#     summary="Connect/Update specified cameras and apply provided configuration settings",
# )
# def cameras_connect_post_endpoint(
#         request: CameraConfigs = Body(..., examples=[default_camera_configs_factory()])
# ):
#     logger.api("Received `skellycam/connect` POST request...")
#     try:
#         get_skellycam_app_controller().connect_to_cameras(camera_configs=request)
#         logger.api("`skellycam/connect` POST request handled successfully.")
#     except Exception as e:
#         logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
#         logger.exception(e)


@connect_cameras_router.get(
    "/connect",
    summary="Detect and connect to all available cameras with default settings",
)
def cameras_connect_get_endpoint():
    logger.api("Received `skellycam/connect` GET request...")
    try:
        get_skellycam_app_controller().connect_to_cameras()
        logger.api("`skellycam/connect` GET request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
        logger.exception(e)
