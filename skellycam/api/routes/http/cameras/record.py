import logging

from fastapi import APIRouter, HTTPException

from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)

record_cameras_router = APIRouter()



@record_cameras_router.get("/record/start",
                           summary="Start recording video from cameras")
async def start_recording() -> bool:
    logger.api("Received `/record/start` request...")
    success = get_controller().start_recording()
    if not success:
        logger.warning("Recording could not be started - check if cameras are connected.")
        raise HTTPException(status_code=409, detail="Recording could not be started - check if cameras are connected.")
    logger.api("`/record/start` request handled successfully.")
    return success


@record_cameras_router.get("/record/stop",
                           summary="Stop recording video from cameras")
async def stop_recording() -> bool:
    logger.api("Received `/record/stop` request...")
    success = get_controller().stop_recording()
    if not success:
        logger.warning(
            "Recording could not be stopped - Either no recording was in progress or cameras are not connected.")
        raise HTTPException(status_code=409,
                            detail="Recording could not be stopped - Either no recording was in progress or cameras are not connected.")
    logger.api("`/record/stop` request handled successfully.")
    return success
