import logging

from fastapi import APIRouter, Body

from skellycam.backend.api_server.requests_responses.connect_to_cameras_request_response import (
    ConnectToCamerasRequest,
    CamerasConnectedResponse,
)
from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)

logger = logging.getLogger(__name__)

http_router = APIRouter()
controller = get_or_create_controller()


@http_router.get("/hello", summary="Simple health check")
async def hello():
    """
    A simple endpoint to greet the user of the SkellyCam API.
    This can be used as a sanity check to ensure the API is responding.
    """
    return {"message": "Hello from the SkellyCam API 💀📸✨"}


@http_router.get(
    "/detect",
    response_model=CamerasDetectedResponse,
    summary="Detect available cameras",
)
def detect_available_cameras() -> CamerasDetectedResponse:
    """
    Detect all available cameras connected to the system.
    This will return a list of cameras that the system can attempt to connect to, along with
    their available resolutions and framerates
    """
    return controller.detect_available_cameras()


@http_router.post(
    "/connect",
)
async def connect_to_cameras(
    request: ConnectToCamerasRequest = Body(
        ..., example=ConnectToCamerasRequest.default().dict()
    ),
):
    logger.info("Connecting to cameras")
    response: CamerasConnectedResponse = controller.connect_to_cameras(
        request.camera_configs
    )
    if response.success:
        logger.info("Connected to cameras!")
        return response
    else:
        logger.error("Failed to connect to cameras")
        return response


#
# @http_router.get(
#     "/cameras/latest_frames",
#     summary="Get the latest synchronized multi-frame from all cameras",
#     responses={200: {"content": {"application/octet-stream": {}}}},
# )
# def get_latest_frames():
#     """
#     Obtain the latest captured frames from each connected camera.
#     Returns the raw bytes of the MultiFramePayload object.
#     """
#     try:
#         latest_multiframe_payload: MultiFramePayload = (
#             controller.camera_group_manager.get_latest_frames()
#         )
#         return StreamingResponse(
#             iter([latest_multiframe_payload.to_bytes()]),
#             media_type="application/octet-stream",
#         )
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))
