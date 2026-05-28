import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig, DEFAULT_CAMERA_ID, CameraConfigs
from skellycam.core.camera_group.camera_group_manager import (
    get_or_create_camera_group_manager,
    USE_RUST_BACKEND,
)
from skellycam.core.device_detection.detect_cameras_devices import CameraDeviceInfo, CameraFormatInfo, detect_available_cameras
from skellycam.core.device_detection.detect_microphone_devices import get_available_microphones
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


class DetectedMicrophonesResponse(BaseModel):
    microphones: dict[int, str]


class StatsSummary(BaseModel):
    median: float
    mean: float
    std: float
    min: float
    max: float


class StopRecordingResponse(BaseModel):
    recording_name: str
    recording_path: str
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    mean_framerate: float
    mean_inter_camera_sync_ms: float
    framerate_stats: StatsSummary
    frame_duration_stats: StatsSummary
    inter_camera_grab_range_ms_stats: StatsSummary


@camera_router.post("/detect", summary="Detect available camera devices")
def cameras_detect_endpoint(
        request: Request,
        filter_virtual: bool = True,
        backend_id: CameraBackendInt | None = None
) -> DetectedCamerasResponse:
    try:
        if USE_RUST_BACKEND:
            cameras = _detect_cameras_rust(filter_virtual=filter_virtual)
        else:
            cameras = detect_available_cameras(backend_id=backend_id, filter_virtual=filter_virtual)

            # Merge format data from the Rust openpnp-capture enumeration.
            # Match by device_path — both OpenCV and openpnp-capture use the
            # same USB device path format on Windows DirectShow.
            try:
                import _skellycam_rust
                rust_cameras = _skellycam_rust.detect_cameras()
                path_to_formats = {
                    rc["device_path"]: rc["formats"]
                    for rc in rust_cameras
                    if rc.get("device_path")
                }
                for cam in cameras:
                    if cam.path and cam.path in path_to_formats:
                        cam.formats = [
                            CameraFormatInfo(
                                width=f["width"],
                                height=f["height"],
                                fps=f["fps"],
                                fourcc=f["fourcc"],
                                fourcc_str=f["fourcc_str"],
                            )
                            for f in path_to_formats[cam.path]
                        ]
            except ImportError:
                logger.debug("_skellycam_rust not available, skipping format enumeration")
            except Exception as e:
                logger.warning(f"Failed to merge Rust format data: {e}")

        return DetectedCamerasResponse(cameras=cameras)
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.get("/microphone/detect", summary="Detect available microphone devices")
def microphone_detect_endpoint(request: Request) -> DetectedMicrophonesResponse:
    try:
        microphones = get_available_microphones()
        return DetectedMicrophonesResponse(microphones=microphones)
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
        camera_group = await get_or_create_camera_group_manager(app=request.app).create_or_update_camera_group(
            camera_configs=configs)

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
        await get_or_create_camera_group_manager(app=request.app).start_recording_all_groups(
            RecordingInfo(**request_body.model_dump()))

        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.get("/group/all/record/stop", summary="Stop recording")
async def stop_recording(request: Request) -> list[StopRecordingResponse]:
    try:
        results = await get_or_create_camera_group_manager(app=request.app).stop_recording_all_groups()

        def _stats_summary(stats_recarray: np.recarray) -> StatsSummary:
            return StatsSummary(
                median=float(stats_recarray.median_value),
                mean=float(stats_recarray.mean_value),
                std=float(stats_recarray.standard_deviation_value),
                min=float(stats_recarray.min_value),
                max=float(stats_recarray.max_value),
            )

        responses = []
        for recording_info, timestamp_stats in results:
            responses.append(StopRecordingResponse(
                recording_name=recording_info.recording_name,
                recording_path=recording_info.full_recording_path,
                number_of_cameras=timestamp_stats.number_of_cameras,
                number_of_frames=timestamp_stats.number_of_frames,
                total_duration_sec=round(timestamp_stats.total_duration_sec, 3),
                mean_framerate=round(float(timestamp_stats.framerate_stats.mean_value), 2),
                mean_inter_camera_sync_ms=round(float(timestamp_stats.inter_camera_grab_range_ms.mean_value), 2),
                framerate_stats=_stats_summary(timestamp_stats.framerate_stats),
                frame_duration_stats=_stats_summary(timestamp_stats.frame_duration_stats),
                inter_camera_grab_range_ms_stats=_stats_summary(timestamp_stats.inter_camera_grab_range_ms),
            ))

        return responses
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_router.delete("/group/close/all", summary="Close all camera groups")
async def close_all_camera_groups(request: Request) -> bool:
    try:
        await get_or_create_camera_group_manager(app=request.app).close_all_camera_groups()
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


# ── Detection helpers ──────────────────────────────────────────────────────────


def _detect_cameras_rust(*, filter_virtual: bool = True) -> list[CameraDeviceInfo]:
    """Detect cameras using the Rust backend (_skellycam_rust.detect_cameras).

    Converts the Rust detection output (list of dicts) to CameraDeviceInfo
    objects. Virtual cameras are filtered out by default.
    """
    import _skellycam_rust

    rust_cameras = _skellycam_rust.detect_cameras()
    results: list[CameraDeviceInfo] = []

    for rc in rust_cameras:
        if filter_virtual and not rc.get("device_path"):
            continue

        formats = [
            CameraFormatInfo(
                width=f["width"],
                height=f["height"],
                fps=f["fps"],
                fourcc=f["fourcc"],
                fourcc_str=f["fourcc_str"],
            )
            for f in rc.get("formats", [])
        ]

        results.append(
            CameraDeviceInfo(
                index=rc["camera_index"],
                name=rc.get("display_name", f"Camera {rc['camera_index']}"),
                path=rc.get("device_path"),
                formats=formats,
            )
        )

    return results
