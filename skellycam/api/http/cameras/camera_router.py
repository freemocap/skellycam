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

camera_router = APIRouter(prefix="/camera", tags=["Cameras"])


class CameraGroupCreateRequest(BaseModel):
    camera_configs: dict[CameraIdString, CameraConfig]

    @classmethod
    def example(cls) -> "CameraGroupCreateRequest":
        return cls(camera_configs={DEFAULT_CAMERA_ID: CameraConfig()})


class CameraUpdateRequest(BaseModel):
    camera_configs: CameraConfigs

    @classmethod
    def example(cls) -> "CameraUpdateRequest":
        return cls(camera_configs={DEFAULT_CAMERA_ID: CameraConfig(exposure=-8)})


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(
        default_factory=default_recording_name,
        description="Name of the recording"
    )
    recording_directory: str = Field(
        default_factory=get_default_recording_folder_path,
        description="Path to save the recording"
    )
    mic_device_index: int = Field(
        default=-1,
        description="Index of the microphone device"
    )

    def recording_full_path(self) -> str:
        return str(Path(self.recording_directory) / self.recording_name)


class CreateCameraGroupResponse(BaseModel):
    group_id: CameraGroupIdString
    camera_configs: CameraConfigs


class DetectedCamerasResponse(BaseModel):
    cameras: list[CameraDeviceInfo]


@camera_router.post("/detect", summary="Detect available camera devices")
def cameras_detect_endpoint(
        request: Request,
        filter_virtual: bool = True,
        backend_id: CameraBackendInt | None = None
) -> DetectedCamerasResponse:
    try:
        cameras = detect_available_cameras(backend_id=backend_id, filter_virtual=filter_virtual)
        return DetectedCamerasResponse(cameras=cameras)
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.post("/group/apply", summary="Create/update camera group")
async def camera_group_apply_post_endpoint(
        request: Request,
        request_body: CameraGroupCreateRequest = Body(..., examples=[CameraGroupCreateRequest.example()])
) -> CreateCameraGroupResponse:
    try:
        raw_body = await request.body()
        logger.info(f"Request to {request.url}: {raw_body.decode('utf-8')}")

        configs = request_body.camera_configs
        camera_group = await get_or_create_camera_group_manager(app=request.app).create_or_update_camera_group(camera_configs=configs)

        return CreateCameraGroupResponse(
            group_id=camera_group.id,
            camera_configs=camera_group.configs
        )
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.post("/group/all/record/start", summary="Start recording")
async def start_recording(
        request: Request,
        request_body: StartRecordingRequest = Body(..., examples=[StartRecordingRequest()])
) -> bool:
    try:
        if request_body.recording_directory.startswith("~"):
            request_body.recording_directory = str(
                Path(request_body.recording_directory.replace("~", str(Path.home()), 1))
            )

        Path(request_body.recording_directory).mkdir(parents=True, exist_ok=True)
        await get_or_create_camera_group_manager(app=request.app).start_recording_all_groups(RecordingInfo(**request_body.model_dump()))

        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.get("/group/all/record/stop", summary="Stop recording")
async def stop_recording(request: Request) -> bool:
    try:
        await get_or_create_camera_group_manager(app=request.app).stop_recording_all_groups()
        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.delete("/group/close/all", summary="Close all camera groups")
def close_all_camera_groups(request: Request) -> bool:
    try:
        get_or_create_camera_group_manager(app=request.app).close_all_camera_groups()
        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.get("/group/all/pause_unpause", summary="Pause/unpause cameras")
async def pause_camera_groups(request: Request) -> bool:
    try:
        await get_or_create_camera_group_manager(app=request.app).pause_unpause_all_groups()
        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
