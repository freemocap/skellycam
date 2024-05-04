import logging

from fastapi import APIRouter

from skellycam.backend.api.models.base_models import BaseResponse, BaseRequest
from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.controller.singleton import get_controller

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


class CamerasConnectedResponse(BaseResponse):
    # TODO: Add camera configs after connecting, and info if the settings match the user's request
    pass


class ConnectCamerasRequest(BaseRequest):
    camera_configs: CameraConfigs


@connect_cameras_router.get(
    "/connect/default",
    response_model=CamerasConnectedResponse,
    summary="Connect to all available cameras using default settings",
)
async def connect_cameras_default_route() -> CamerasConnectedResponse:
    controller = get_controller()
    logger.info("Detecting available cameras...")
    try:
        return CamerasConnectedResponse(await controller.connect())
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        raise e


@connect_cameras_router.post(
    "/connect",
    response_model=CamerasConnectedResponse,
    summary="Connect to all available cameras using user provided camera configs",
)
async def connect_cameras_route(request: ConnectCamerasRequest) -> CamerasConnectedResponse:
    controller = get_controller()
    logger.info("Detecting available cameras...")
    try:
        return CamerasConnectedResponse(await controller.connect(request.camera_configs))
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        raise e
