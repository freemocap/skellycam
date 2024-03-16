import base64
import json
import logging

import cv2
from fastapi import APIRouter, Body

from skellycam.backend.api_server.requests_responses.connect_to_cameras_request_response import (
    ConnectToCamerasRequest,
    CamerasConnectedResponse,
)
from skellycam.backend.api_server.requests_responses.start_recording_request import (
    StartRecordingRequest,
)
from skellycam.backend.controller import get_or_create_controller
from skellycam.backend.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.frames.multi_frame_payload import (
    MultiFramePayload,
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
    logger.info("Detecting available cameras...")
    try:
        return controller.detect_available_cameras()
    except Exception as e:
        logger.error(f"Failed to detect available cameras: {e}")
        logger.exception(e)
        raise e


@http_router.post(
    "/connect",
)
async def connect_to_cameras(
    request: ConnectToCamerasRequest = Body(
        ..., examples=[ConnectToCamerasRequest.default().dict()]
    ),
):
    logger.info("Connecting to cameras")
    try:
        response: CamerasConnectedResponse = controller.connect_to_cameras(
            request.camera_configs
        )
        if response.success:
            logger.info("Connected to cameras!")
            return response
        else:
            logger.error("Failed to connect to cameras")
            return response
    except Exception as e:
        logger.error(f"Failed to connect to cameras: {e}")
        logger.exception(e)
        raise e


@http_router.get("/close", summary="Close all connected cameras")
def close_cameras():
    """
    Close all connected cameras.
    This will release all resources and stop capturing frames from all connected cameras.
    """
    logger.info("Closing cameras...")
    try:
        controller.close_cameras()
        return {"message": "Cameras closed"}
    except Exception as e:
        logger.error(f"Failed to close cameras: {e}")
        logger.exception(e)
        raise e


@http_router.get(
    "/latest_frames",
    summary="Get the latest synchronized multi-frame from all cameras",
)
def get_latest_frames():
    """
    Obtain the latest captured frames from each connected camera.
    Returns the raw bytes of the MultiFramePayload object.
    """
    if not controller.camera_group_manager:
        response = {
            "message": "Camera group has not been initialized - cannot get latest frames, call `detect_available_cameras` then `connect_to_cameras`."
        }
        logger.error(response["message"])
        return response
    try:
        latest_multiframe_payload: MultiFramePayload = (
            controller.camera_group_manager.get_latest_frames()
        )
        if not latest_multiframe_payload:
            logger.trace("No frames to send - returning nothing.")
            return None

        simple_payload = {
            camera_id: frame.raw_image.get_image()
            for camera_id, frame in latest_multiframe_payload.frames.items()
        }

        # convert numpy images to base64 jpeg compressed images
        compressed_payload = {}
        for camera_id, image in simple_payload.items():
            _, buffer = cv2.imencode(".jpg", image)
            compressed_payload[camera_id] = base64.b64encode(buffer).decode("utf-8")
        return json.dumps(compressed_payload)
    except Exception as e:
        raise Exception(f"Failed to get latest frames: {e}")


@http_router.post(
    "/start_recording",
    summary="Start recording videos from all connected cameras",
)
def start_recording(request: StartRecordingRequest):
    """
    Start recording videos from all connected cameras.
    """
    logger.info(f"Starting recording videos to: {request.recording_folder_path}")
    try:
        controller.start_recording(request.recording_folder_path)
        return {"message": "Recording started"}
    except Exception as e:
        raise Exception(f"Failed to start recording: {e}")


@http_router.get(
    "/stop_recording",
    summary="Stop recording videos from all connected cameras",
)
def start_recording():
    """
    Stop recording videos from all connected cameras.
    """
    logger.info(f"Stopping recording videos...")
    try:
        controller.stop_recording()
        return {"message": "Recording stopped"}
    except Exception as e:
        logger.error(f"Error when stopping recording: {e}")
        logger.exception(e)
        raise Exception(f"Failed to stop recording: {e}")


@http_router.post(
    "/update_camera_configs",
    summary="Update camera configurations",
)
def update_camera_configs(camera_configs: CameraConfigs):
    """
    Update camera configurations.
    """
    logger.info(f"Received camera configurations {camera_configs} - updating...")
    try:
        response = controller.update_camera_configs(camera_configs)
        return response
    except Exception as e:
        raise Exception(f"Failed to update camera configurations: {e}")
