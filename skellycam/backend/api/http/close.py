import logging

from fastapi import APIRouter

from skellycam.backend.api.models.base_models import BaseResponse
from skellycam.backend.core.controller.singleton import get_or_create_controller

logger = logging.getLogger(__name__)

camera_close_router = APIRouter()


class CamerasClosedResponse(BaseResponse):
    pass


@camera_close_router.get("/close",
                         response_model=CamerasClosedResponse,
                         summary="Close camera connections")
async def close_camera_connections():
    logger.api("Received `/close` request...")

    controller = get_or_create_controller()
    try:
        await controller.close()
        logger.api("`/close` request handled successfully.")
        return CamerasClosedResponse()
    except Exception as e:
        logger.error(f"Failed to close cameras: {type(e).__name__} - {e}")
        logger.exception(e)
        return CamerasClosedResponse.from_exception(e)
