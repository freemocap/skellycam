import logging
from typing import Optional

from fastapi import APIRouter, Body
from pydantic import Field

from skellycam.api.models.base_models import BaseRequest
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs, default_camera_configs_factory
from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


class ConnectCamerasRequest(BaseRequest):
    camera_configs: Optional[CameraConfigs] = Field(default_factory=default_camera_configs_factory)


@connect_cameras_router.post(
    "/connect/apply",

    summary="Connect/Update specified cameras and apply provided configuration settings",
)
async def cameras_apply_config_route(
        request: ConnectCamerasRequest = Body(..., examples=[ConnectCamerasRequest()])
):
    logger.api("Received `/connect/apply` POST request...")
    try:
        await get_controller().connect_to_cameras(
            camera_configs=request.camera_configs)
        logger.api("`/connect/apply` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)


@connect_cameras_router.get(
    "/connect",
    summary="Connect to all available cameras with default settings",
)
async def cameras_connect_route():
    logger.api("Received `/connect` GET request...")
    try:
        await get_controller().connect_to_cameras()
        logger.api("`/connect` GET request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
        logger.exception(e)
