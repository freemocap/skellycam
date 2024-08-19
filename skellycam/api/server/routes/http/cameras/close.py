import logging

from fastapi import APIRouter

from skellycam.api.server.models.base_models import BaseResponse
from skellycam.core.camera_group_manager import CameraGroupManager, get_camera_group_manager

logger = logging.getLogger(__name__)

close_cameras_router = APIRouter(

)


class CamerasClosedResponse(BaseResponse):
    pass


@close_cameras_router.get("/close",
                          response_model=CamerasClosedResponse,
                          summary="Close camera connections")
async def close_camera_connections():
    logger.api("Received `/close` request...")

    controller: CameraGroupManager = get_camera_group_manager()
    try:
        await controller.close()
        logger.api("`/close` request handled successfully.")
        return CamerasClosedResponse()
    except Exception as e:
        logger.error(f"Failed to close cameras: {type(e).__name__} - {e}")
        logger.exception(e)
        return CamerasClosedResponse.from_exception(e)
