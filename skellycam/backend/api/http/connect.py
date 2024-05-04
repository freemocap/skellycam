import logging

from fastapi import APIRouter, Body

from skellycam.backend.api.models.base_models import BaseResponse, BaseRequest
from skellycam.backend.core.cameras.config.camera_config import CameraConfigs, CameraConfig
from skellycam.backend.core.controller.singleton import get_or_create_controller
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


class CamerasConnectedResponse(BaseResponse):
    # TODO: Add camera configs after connecting, and info if the settings match the user's request
    pass


class ConnectCamerasRequest(BaseRequest):
    camera_configs: CameraConfigs
    @classmethod
    def default(cls):
        return cls(camera_configs={CameraId(0): CameraConfig(camera_id=0)})


@connect_cameras_router.get(
    "/connect/all",
    response_model=CamerasConnectedResponse,
    summary="Connect to all available cameras using default settings",
)
async def connect_cameras_default_route() -> CamerasConnectedResponse:
    controller = get_or_create_controller()
    logger.api("Received `/connect/all` request...")
    try:
        await controller.connect()
        logger.success("`/connect/all` request handled successfully.")
        return CamerasConnectedResponse()
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        return CamerasConnectedResponse.from_exception(e)


@connect_cameras_router.post(
    "/connect",
    response_model=CamerasConnectedResponse,
    summary="Connect to cameras specified in the request",
)
async def connect_cameras_route(
        request: ConnectCamerasRequest = Body(..., examples=[ConnectCamerasRequest.default()])
) -> CamerasConnectedResponse:
    controller = get_or_create_controller()
    logger.info("Detecting available cameras...")
    try:
        await controller.connect(request.camera_configs)
        return CamerasConnectedResponse()
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        raise e
