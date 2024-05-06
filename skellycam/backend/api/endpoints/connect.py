import logging
from typing import Optional, List

from fastapi import APIRouter, Body

from skellycam.backend.api.models.base_models import BaseResponse, BaseRequest
from skellycam.backend.core.cameras.config.camera_config import CameraConfigs, CameraConfig
from skellycam.backend.core.controller.singleton import get_or_create_controller
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)

camera_connection_router = APIRouter()


class CamerasConnectedResponse(BaseResponse):
    connected_cameras: Optional[List[CameraId]]


class ConnectCamerasRequest(BaseRequest):
    camera_configs: CameraConfigs
    @classmethod
    def default(cls):
        return cls(camera_configs={CameraId(0): CameraConfig(camera_id=0)})

@camera_connection_router.post(
    "/connect",
    response_model=CamerasConnectedResponse,
    summary="Connect to cameras specified in the request",
)
async def connect_cameras_route(
        request: ConnectCamerasRequest = Body(..., examples=[ConnectCamerasRequest.default()])
) -> CamerasConnectedResponse:
    controller = get_or_create_controller()
    logger.api("Received `/connect` POST request...")
    try:
        connected_cameras = await controller.connect(request.camera_configs)
        logger.api("`/connect` POST request handled successfully.")
        return CamerasConnectedResponse(connected_cameras=connected_cameras)
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        return CamerasConnectedResponse.from_exception(e)


@camera_connection_router.get(
    "/connect",
    response_model=CamerasConnectedResponse,
    summary="Connect to all available cameras with default settings",
)
async def connect_cameras_route() -> CamerasConnectedResponse:
    controller = get_or_create_controller()
    logger.api("Received `/connect` GET request...")
    try:
        connected_cameras = await controller.connect()
        logger.api("`/connect` GET request handled successfully.")
        return CamerasConnectedResponse(connected_cameras=connected_cameras)
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
        logger.exception(e)
        return CamerasConnectedResponse.from_exception(e)


