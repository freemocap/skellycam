import logging
from typing import Optional, List

from fastapi import APIRouter, Body
from pydantic import Field

from skellycam.api.models.base_models import BaseResponse, BaseRequest
from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config_model import CameraConfigs, default_camera_configs_factory
from skellycam.core.controller.singleton import get_or_create_controller

logger = logging.getLogger(__name__)

camera_connection_router = APIRouter()


class CamerasConnectedResponse(BaseResponse):
    connected_cameras: Optional[List[CameraId]] = None


class ConnectCamerasRequest(BaseRequest):
    camera_configs: Optional[CameraConfigs] = Field(default_factory=default_camera_configs_factory)

@camera_connection_router.post(
    "/connect",
    response_model=CamerasConnectedResponse,
    summary="Connect to cameras specified in the request",
)
async def connect_cameras_route(
        request: ConnectCamerasRequest = Body(..., examples=[ConnectCamerasRequest()])
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


@camera_connection_router.get(
    "/connect/test",
    response_model=BaseResponse,
    summary="Test camera connection by recording a set number of frames",
)
async def test_camera_connection(number_of_frames: int = 10) -> BaseResponse:
    controller = get_or_create_controller()
    logger.api("Received `/connect/test` GET request...")
    try:
        # Record for the specified number of frames
        connected_cameras = await controller.connect(number_of_frames=number_of_frames)
        logger.api("`/connect/test` GET request handled successfully.")
        return CamerasConnectedResponse(connected_cameras=connected_cameras)
    except Exception as e:
        logger.error(f"Error during camera test recording: {type(e).__name__} - {e}")
        logger.exception(e)
        return CamerasConnectedResponse.from_exception(e)
