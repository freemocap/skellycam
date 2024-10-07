import logging

from fastapi import APIRouter, Body

from skellycam.api.app.app_state import get_app_state
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs, default_camera_configs_factory
from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


@connect_cameras_router.post(
    "/connect/apply",

    summary="Connect/Update specified cameras and apply provided configuration settings",
)
async def cameras_apply_config_route(
        request: CameraConfigs = Body(..., examples=[default_camera_configs_factory()])
):
    logger.api("Received `/connect/apply` POST request...")
    try:
        await get_controller().connect_to_cameras(camera_configs=request)
        logger.api("`/connect/apply` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)


@connect_cameras_router.get(
    "/connect/detect",
    summary="Detect and connect to all available cameras with default settings",
)
async def detect_and_connect_to_cameras_route():
    logger.api("Received `/connect` GET request...")
    try:
        await get_controller().connect_to_cameras()
        logger.api("`/connect` GET request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
        logger.exception(e)
