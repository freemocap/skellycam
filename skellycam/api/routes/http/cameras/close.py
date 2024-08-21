import logging

from fastapi import APIRouter

from skellycam.api.models.base_models import BaseResponse
from skellycam.core.controller import Controller, get_controller

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

    controller: Controller = get_controller()
    try:
        await controller.close_cameras()
        logger.api("`/close` request handled successfully.")
        return CamerasClosedResponse()
    except Exception as e:
        logger.error(f"Failed to close cameras: {type(e).__name__} - {e}")
        logger.exception(e)
        return CamerasClosedResponse.from_exception(e)
