import logging

from fastapi import APIRouter

from skellycam.backend.core.device_detection.detect_available_cameras import CamerasDetectedResponse

logger = logging.getLogger(__name__)

camera_router = APIRouter()
# controller = get_or_create_controller()


@camera_router.get(
    "/detect",
    response_model=CamerasDetectedResponse,
    summary="Detect available cameras",
    description="Detect all available cameras connected to the system. "
                "This will return a list of cameras that the system can attempt to connect to, "
                "along with their available resolutions and framerates",
)
async def detect_cameras_route() -> CamerasDetectedResponse:
    global controller
    logger.info("Detecting available cameras...")
    try:
        # return await controller.detect()
        return {"message": "Cameras detected"}
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        raise e




# @camera_router.get("/close",
#                    summary="Close camera connections")
# async def close_camera_connections():
#     global controller
#     if not controller.connected:
#         return {"message": "No camera connections to close"}
#     logger.info("Closing camera connections...")
#     await controller.close()
#     return {"message": "Camera connections closed"}


# @camera_router.get("/show",
#                    summary="Show camera views in cv2 windows")
# async def show_camera_windows():
#     global controller
#     if not controller.connected:
#         return {"message": "No camera connections to show"}
#     logger.info("Showing camera windows...")
#     controller.show_camera_windows()
#     return {"message": "Camera viewer started"}
