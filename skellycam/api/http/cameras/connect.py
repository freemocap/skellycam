import logging

from fastapi import APIRouter, Body

from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, default_camera_configs_factory

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


@connect_cameras_router.post(
    "/connect/apply",

    summary="Connect/Update specified cameras and apply provided configuration settings",
)
def cameras_apply_config_route(
        request: CameraConfigs = Body(..., examples=[default_camera_configs_factory()])
):
    logger.api("Received `skellycam/cameras/connect/apply` POST request...")
    try:
        get_skellycam_app_controller().connect_to_cameras(camera_configs=request)
        logger.api("`skellycam/cameras/connect/apply` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)


@connect_cameras_router.get(
    "/connect/detect",
    summary="Detect and connect to all available cameras with default settings",
)
def detect_and_connect_to_cameras_route():
    logger.api("Received `skellycam/cameras/connect` GET request...")
    try:
        get_skellycam_app_controller().connect_to_cameras()
        logger.api("`skellycam/cameras/connect` GET request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
        logger.exception(e)
