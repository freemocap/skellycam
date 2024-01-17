from fastapi import APIRouter, Body, BackgroundTasks, HTTPException
from starlette.responses import StreamingResponse

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.controller.interactions.connect_to_cameras import (
    CamerasConnectedResponse,
    ConnectToCamerasRequest,
)
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload

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
    status_code=202,
    summary="Connect to specified cameras in a BackgroundTask",
)
async def connect_to_cameras(
    background_tasks: BackgroundTasks,
    request: ConnectToCamerasRequest = Body(
        ..., example=ConnectToCamerasRequest.default().dict()
    ),
):
    """
    Connect to cameras as specified in the ConnectToCamerasRequest payload. Asynchronously using BackgroundTasks.
    """
    # Add the controller's connect function to background tasks
    background_tasks.add_task(controller.connect_to_cameras, request.camera_configs)

    # Return a message acknowledging the task has been started
    return CamerasConnectedResponse(success=True)


@http_router.get(
    "/cameras",
    response_model=CameraConfigs,
    summary="Get configurations of connected cameras",
)
def get_cameras() -> CameraConfigs:
    """
    Retrieve the current configurations for all connected cameras.
    This includes parameters set for each individual camera.
    """
    return controller.camera_group_manager.camera_configs


@http_router.get(
    "/cameras/latest_frames",
    summary="Get the latest synchronized multi-frame from all cameras",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def get_latest_frames():
    """
    Obtain the latest captured frames from each connected camera.
    Returns the raw bytes of the MultiFramePayload object.
    """
    try:
        latest_multiframe_payload: MultiFramePayload = (
            controller.camera_group_manager.get_latest_frames()
        )
        return StreamingResponse(
            iter([latest_multiframe_payload.to_bytes()]),
            media_type="application/octet-stream",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
