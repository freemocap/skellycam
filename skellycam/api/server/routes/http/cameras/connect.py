import logging
from typing import Optional

from fastapi import APIRouter, Body
from pydantic import Field

from skellycam.api.server.models.base_models import BaseResponse, BaseRequest
from skellycam.core.camera_group_manager import CameraGroupManager, get_camera_group_manager
from skellycam.core.cameras.config.camera_config import CameraConfigs, default_camera_configs_factory
from skellycam.core.detection.camera_device_info import AvailableDevices

logger = logging.getLogger(__name__)

connect_cameras_router = APIRouter()


class ConnectCamerasResponse(BaseResponse):
    connected_cameras: Optional[CameraConfigs] = None
    detected_cameras: Optional[AvailableDevices] = None


class ConnectCamerasRequest(BaseRequest):
    camera_configs: Optional[CameraConfigs] = Field(default_factory=default_camera_configs_factory)


@connect_cameras_router.post(
    "/connect",
    response_model=ConnectCamerasResponse,
    summary="Connect to cameras specified in the request",
)
async def connect_cameras_route(
        request: ConnectCamerasRequest = Body(..., examples=[ConnectCamerasRequest()])
) -> ConnectCamerasResponse:
    controller: CameraGroupManager = get_camera_group_manager()

    logger.api("Received `/connect` POST request...")
    try:
        connected_cameras, available_devices = await controller.connect_to_cameras(request.camera_configs)
        logger.api("`/connect` POST request handled successfully.")
        return ConnectCamerasResponse(connected_cameras=connected_cameras,
                                      detected_cameras=available_devices)
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        return ConnectCamerasResponse.from_exception(e)


@connect_cameras_router.get(
    "/connect",
    response_model=ConnectCamerasResponse,
    summary="Connect to all available cameras with default settings",
)
async def connect_cameras_route() -> ConnectCamerasResponse:
    camera_group_manager: CameraGroupManager = get_camera_group_manager()

    logger.api("Received `/connect` GET request...")
    try:
        connected_cameras, available_devices = await camera_group_manager.connect_to_cameras()
        logger.api("`/connect` GET request handled successfully.")
        return ConnectCamerasResponse(connected_cameras=connected_cameras,
                                      detected_cameras=available_devices)
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {type(e).__name__} - {e}")
        logger.exception(e)
        return ConnectCamerasResponse.from_exception(e)


@connect_cameras_router.get(
    "/connect/test",
    response_model=BaseResponse,
    summary="Test camera connection by recording a set number of frames",
)
async def test_camera_connection(number_of_frames: int = 10) -> BaseResponse:
    controller: CameraGroupManager = get_camera_group_manager()

    logger.api("Received `/connect/test` GET request...")
    try:
        # Record for the specified number of frames
        connected_cameras = await controller.connect(number_of_frames=number_of_frames)
        logger.api("`/connect/test` GET request handled successfully.")
        return ConnectCamerasResponse(connected_cameras=connected_cameras)
    except Exception as e:
        logger.error(f"Error during camera test recording: {type(e).__name__} - {e}")
        logger.exception(e)
        return ConnectCamerasResponse.from_exception(e)
