import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfig, DEFAULT_CAMERA_ID, CameraConfigs
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString
from skellycam.skellycam_app.skellycam_app import get_skellycam_app
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


@camera_router.post("/group/create",
                    summary="Create camera group with provided configuration settings",
                    )
def camera_group_create_post_endpoint(
        request: CameraGroupCreateRequest = Body(...,
                                                 description="Request body containing desired camera configuration",
                                                 examples=[
                                                     CameraGroupCreateRequest.example()]), ) -> CreateCameraGroupResponse :
    logger.api(f"Received `skellycam/cameras/group/create` POST request with config:  {request.camera_configs}...")
    try:
        configs = request.camera_configs
        camera_group = get_skellycam_app().create_camera_group(camera_configs=configs)
        logger.api("`skellycam/cameras/group/create` POST request handled successfully.")
        return CreateCameraGroupResponse(group_id=camera_group.id,
                                         camera_configs=camera_group.configs)
    except Exception as e:
        logger.error(f"Error when processing `skellycam/cameras/group/create` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                             detail=f"Error when processing `skellycam/cameras/group/create` request: {type(e).__name__} - {e}")


@camera_router.post("/group/all/record/start",
                            summary="Start recording video from all camera groups")
def start_recording(request: StartRecordingRequest = Body(..., examples=[StartRecordingRequest()])):
    logger.api("Received `/record/start` request...")
    if request.recording_directory.startswith("~"):
        request.recording_directory = str(Path(request.recording_directory.replace("~", str(Path.home()), 1)))
    Path(request.recording_directory).mkdir(parents=True, exist_ok=True)
    get_skellycam_app().start_recording(RecordingInfo(**request.model_dump()))
    logger.api("`/record/start` request handled successfully.")
    return True


@camera_router.get("/group/all/record/stop",
                           summary="Stop recording video from camera groups")
def stop_recording():
    logger.api("Received `/record/stop` request...")
    get_skellycam_app().stop_recording()
    logger.api("`/record/stop` request handled successfully.")


@camera_router.delete(
    "/group/close/all",
    summary="Close all camera groups and their associated cameras",
)
def camera_group_close_all_delete_endpoint():
    logger.api("Received `/camera/group/close/all` DELETE request to close all camera groups...")

    try:
        get_skellycam_app().close_all_camera_groups()
        logger.api("`/camera/group/close/all` request handled successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to close all camera groups: {type(e).__name__} - {e}")
        logger.exception(e)
        return HTTPException(status_code=500,
                             detail=f"Error when processing `/camera/group/close/all` request: {type(e).__name__} - {e}")


@camera_router.put(
    "/update",
    summary="Update specified camera and apply provided configuration settings")
def camera_update_put_endpoint(
        request: CameraUpdateRequest = Body(..., description="Request body containing a dictionary of camera configurations keyed by camera IDs",
                                            examples=[CameraUpdateRequest.example()])) -> CameraConfigs:
    logger.api(
        f"Received `cameras/update` PUT request with cameras configs for cameras: {list(request.camera_configs.keys())}...")
    try:
        extracted_configs = get_skellycam_app().camera_group_manager.update_camera_settings(camera_configs=request.camera_configs)
        logger.api("`skellycam/connect` POST request handled successfully.")
        return extracted_configs
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                             detail=f"Error when processing `/camera/update` request: {type(e).__name__} - {e}")


@camera_router.get("/group/all/pause",
                  summary="Pause all camera groups")
def pause_camera_groups():
    logger.api("Received `/pause` request...")
    get_skellycam_app().pause_camera_groups()
    logger.api("`/pause` request handled successfully.")
    return True

@camera_router.get("/group/all/unpause",
                  summary="Unpause all camera groups")
def unpause_camera_groups():
    logger.api("Received `/unpause` request...")
    get_skellycam_app().unpause_camera_groups()
    logger.api("`/unpause` request handled successfully.")
    return True