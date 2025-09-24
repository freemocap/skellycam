import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfig, DEFAULT_CAMERA_ID, CameraConfigs
from skellycam.core.camera_group.camera_group_manager import get_or_create_camera_group_manager
from skellycam.core.device_detection.detect_cameras_devices import CameraDeviceInfo, detect_available_cameras
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString, CameraBackendInt
from skellycam.system.default_paths import default_recording_name, get_default_recording_folder_path

logger = logging.getLogger(__name__)

camera_router = APIRouter(prefix=f"/camera",
                          tags=["Cameras"])


class CameraGroupCreateRequest(BaseModel):
    camera_configs: dict[CameraIdString, CameraConfig]

    @classmethod
    def example(cls):
        return cls(camera_configs={DEFAULT_CAMERA_ID: CameraConfig()})


class CameraUpdateRequest(BaseModel):
    camera_configs: CameraConfigs

    @classmethod
    def example(cls) -> "CameraUpdateRequest":
        return cls(camera_configs={DEFAULT_CAMERA_ID: CameraConfig(exposure=-8)})


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(default_factory=default_recording_name,
                                description="Name of the recording")
    recording_directory: str = Field(default_factory=get_default_recording_folder_path,
                                     description="Path to save the recording ")
    mic_device_index: int = Field(default=-1,
                                  description="Index of the microphone device to record audio from (0 for default, -1 for no audio recording)")

    def recording_full_path(self):
        return str(Path(self.recording_directory) / self.recording_name)


class CreateCameraGroupResponse(BaseModel):
    group_id: CameraGroupIdString
    camera_configs: CameraConfigs


class DetectedCamerasResponse(BaseModel):
    cameras: list[CameraDeviceInfo]


@camera_router.post("/detect",
                    summary="Detect available camera devices",
                    )
def cameras_detect_endpoint(
        request: Request,
        filter_virtual: bool = True,
                            backend_id: CameraBackendInt | None = None) -> DetectedCamerasResponse:
    try:
        cameras = detect_available_cameras(backend_id=backend_id, filter_virtual=filter_virtual)
        return DetectedCamerasResponse(cameras=cameras)
    except Exception as e:
        logger.error(f"Error when processing {request.url}request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing {request.url}request: {type(e).__name__} - {e}")


@camera_router.post("/group/apply",
                    summary="Create camera group with provided configuration settings or update existing group"
                    )
def camera_group_apply_post_endpoint(
        request: Request,
        request_body: CameraGroupCreateRequest = Body(...,
                                                      description="Request body containing desired camera configuration",
                                                      examples=[
                                                     CameraGroupCreateRequest.example()]), ) -> CreateCameraGroupResponse:
    try:
        configs = request_body.camera_configs
        camera_group = get_or_create_camera_group_manager(request.app.state.global_kill_flag).create_and_start_camera_group(camera_configs=configs)
        response = CreateCameraGroupResponse(group_id=camera_group.id,
                                             camera_configs=camera_group.configs)
        return response
    except Exception as e:
        logger.error(f"Error when processing `skellycam/cameras/group/create` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `skellycam/cameras/group/create` request: {type(e).__name__} - {e}")


@camera_router.post("/group/all/record/start",
                    summary="Start recording video from all camera groups")
def start_recording(request:Request,
                    request_body: StartRecordingRequest = Body(..., examples=[StartRecordingRequest()])):
    if request_body.recording_directory.startswith("~"):
        request_body.recording_directory = str(Path(request_body.recording_directory.replace("~", str(Path.home()), 1)))
    Path(request_body.recording_directory).mkdir(parents=True, exist_ok=True)
    get_or_create_camera_group_manager(request.app.state.global_kill_flag).start_recording_all_groups(RecordingInfo(**request_body.model_dump()))
    return True


@camera_router.get("/group/all/record/stop",
                   summary="Stop recording video from camera groups")
def stop_recording(request: Request):
    get_or_create_camera_group_manager(request.app.state.global_kill_flag).stop_recording_all_groups()
    return True


@camera_router.delete(
    "/group/close/all",
    summary="Close all camera groups and their associated cameras",
)
def camera_group_close_all_delete_endpoint(request: Request):
    try:
        get_or_create_camera_group_manager(request.app.state.global_kill_flag).close_all_camera_groups()
        return True
    except Exception as e:
        logger.error(f"Failed to close all camera groups: {type(e).__name__} - {e}")
        logger.exception(e)
        return HTTPException(status_code=500,
                             detail=f"Error when processing {request.url} request: {type(e).__name__} - {e}")


@camera_router.put(
    "/update",
    summary="Update specified camera and apply provided configuration settings")
def camera_update_put_endpoint(
        request: Request,
        request_body: CameraUpdateRequest = Body(...,
                                                 description="Request body containing a dictionary of camera configurations keyed by camera IDs",
                                                 examples=[CameraUpdateRequest.example()])) -> CameraConfigs:
    try:
        extracted_configs = get_or_create_camera_group_manager(request.app.state.global_kill_flag).update_camera_settings(
            camera_configs=request_body.camera_configs)
        return extracted_configs
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `/camera/update` request: {type(e).__name__} - {e}")


@camera_router.get("/group/all/pause_unpause",
                   summary="Pause/Unpause all camera groups")
def pause_camera_groups(request: Request):
    get_or_create_camera_group_manager(request.app.state.global_kill_flag).pause_unpause_all_groups()
    return True
