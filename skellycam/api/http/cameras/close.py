import logging

from fastapi import APIRouter

from skellycam.api.models.base_models import BaseResponse
from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

close_cameras_router = APIRouter()


class CamerasClosedResponse(BaseResponse):
    pass


@close_cameras_router.get("/close",
                          summary="Close camera connections")
async def close_camera_connections():
    logger.api("Received `/close` request...")

    try:
        await get_controller().close_cameras()
        logger.api("`/close` request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to close cameras: {type(e).__name__} - {e}")
        logger.exception(e)
