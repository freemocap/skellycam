"""
Camera group resources — HTTP control plane.

Per-group:
  GET    /camera-groups                        → list all groups + statuses
  PUT    /camera-groups/{group_id}             → create/update group → 200
  DELETE /camera-groups/{group_id}             → disconnect group → 204
  POST   /camera-groups/{group_id}/recording   → start recording → 201
  DELETE /camera-groups/{group_id}/recording   → stop recording → 200
  POST   /camera-groups/{group_id}/pause       → pause → 204
  POST   /camera-groups/{group_id}/unpause     → unpause → 204

All-groups shortcuts (registered before /{group_id} to avoid "all" being matched as an id):
  DELETE /camera-groups/all                    → close all → 204
  POST   /camera-groups/all/recording          → start recording on all → 201
  DELETE /camera-groups/all/recording          → stop recording on all → 200
  POST   /camera-groups/all/pause              → pause all → 204
  POST   /camera-groups/all/unpause            → unpause all → 204
"""
import logging
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, Body, HTTPException, Request, Response
from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import DEFAULT_CAMERA_ID, CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera_group_manager import get_or_create_camera_group_manager
from skellycam.core.camera_group.camera_group_state_machine import (
    CameraGroupStatus,
    InvalidTransitionError,
)
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.system.default_paths import default_recording_name, get_default_recording_folder_path

logger = logging.getLogger(__name__)

camera_group_router = APIRouter(prefix="/camera-groups", tags=["Camera Groups"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CameraGroupCreateRequest(BaseModel):
    camera_configs: CameraConfigs

    @classmethod
    def example(cls) -> "CameraGroupCreateRequest":
        return cls(camera_configs={DEFAULT_CAMERA_ID: CameraConfig()})


class CameraGroupResponse(BaseModel):
    group_id: CameraGroupIdString
    camera_configs: CameraConfigs
    status: str


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(default_factory=default_recording_name)
    recording_directory: str = Field(default_factory=get_default_recording_folder_path)
    mic_device_index: int = -1


class StartRecordingResponse(BaseModel):
    recording_id: str


class StatsSummary(BaseModel):
    median: float
    mean: float
    std: float
    min: float
    max: float

    @classmethod
    def from_recarray(cls, stats: np.recarray, precision: int = 3) -> "StatsSummary":
        return cls(
            median=round(float(stats.median_value), precision),
            mean=round(float(stats.mean_value), precision),
            std=round(float(stats.standard_deviation_value), precision),
            min=round(float(stats.min_value), precision),
            max=round(float(stats.max_value), precision),
        )


class RecordingStopEntry(BaseModel):
    recording_name: str
    recording_path: str
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    mean_framerate: float
    framerate_stats: StatsSummary
    frame_duration_stats: StatsSummary
    inter_camera_grab_range_ms_stats: StatsSummary


class StopRecordingResponse(BaseModel):
    recordings: list[RecordingStopEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cgm(request: Request):
    return get_or_create_camera_group_manager(app=request.app)


def _handle_invalid_transition(e: InvalidTransitionError):
    raise HTTPException(status_code=409, detail=str(e))


def _build_recording_info(body: StartRecordingRequest) -> RecordingInfo:
    directory = body.recording_directory
    if directory.startswith("~"):
        directory = str(Path(directory.replace("~", str(Path.home()), 1)))
    Path(directory).mkdir(parents=True, exist_ok=True)
    return RecordingInfo(
        recording_name=body.recording_name,
        recording_directory=directory,
        mic_device_index=body.mic_device_index,
    )


def _build_stop_response(results) -> StopRecordingResponse:
    entries = []
    for recording_info, timestamp_stats in results:
        entries.append(RecordingStopEntry(
            recording_name=recording_info.recording_name,
            recording_path=recording_info.full_recording_path,
            number_of_cameras=timestamp_stats.number_of_cameras,
            number_of_frames=timestamp_stats.number_of_frames,
            total_duration_sec=round(timestamp_stats.total_duration_sec, 3),
            mean_framerate=round(float(timestamp_stats.framerate_stats.mean_value), 2),
            framerate_stats=StatsSummary.from_recarray(timestamp_stats.framerate_stats),
            frame_duration_stats=StatsSummary.from_recarray(timestamp_stats.frame_duration_stats),
            inter_camera_grab_range_ms_stats=StatsSummary.from_recarray(timestamp_stats.inter_camera_grab_range_ms),
        ))
    return StopRecordingResponse(recordings=entries)


# ---------------------------------------------------------------------------
# All-groups routes  (must be registered BEFORE /{group_id} routes)
# ---------------------------------------------------------------------------

@camera_group_router.get("", summary="List all camera groups and their statuses")
def list_camera_groups(request: Request) -> dict:
    return _get_cgm(request).to_state_dict()


@camera_group_router.delete(
    "/all",
    summary="Close all camera groups",
    status_code=204,
)
async def delete_all_camera_groups(request: Request) -> Response:
    try:
        cgm = _get_cgm(request)
        for group in cgm.camera_groups.values():
            group.state_machine.force_disconnect()
        await cgm.close_all_camera_groups()
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error closing all camera groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.post(
    "/all/recording",
    summary="Start recording on all camera groups",
    status_code=201,
    response_model=StartRecordingResponse,
)
async def start_recording_all(
    request: Request,
    body: StartRecordingRequest = Body(default_factory=StartRecordingRequest),
) -> StartRecordingResponse:
    try:
        cgm = _get_cgm(request)
        recording_info = _build_recording_info(body)
        for group in cgm.camera_groups.values():
            try:
                group.state_machine.transition(CameraGroupStatus.RECORDING)
            except InvalidTransitionError as e:
                _handle_invalid_transition(e)
        await cgm.start_recording_all_groups(recording_info)
        return StartRecordingResponse(recording_id=recording_info.recording_uuid)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting recording on all groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.delete(
    "/all/recording",
    summary="Stop recording on all camera groups",
    response_model=StopRecordingResponse,
)
async def stop_recording_all(request: Request) -> StopRecordingResponse:
    try:
        cgm = _get_cgm(request)
        results = await cgm.stop_recording_all_groups()
        for group in cgm.camera_groups.values():
            try:
                group.state_machine.transition(CameraGroupStatus.STREAMING)
            except InvalidTransitionError as e:
                _handle_invalid_transition(e)
        return _build_stop_response(results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping recording on all groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.post("/all/pause", summary="Pause all camera groups", status_code=204)
def pause_all(request: Request) -> Response:
    try:
        _get_cgm(request).pause_all_groups()
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error pausing all groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.post("/all/unpause", summary="Unpause all camera groups", status_code=204)
def unpause_all(request: Request) -> Response:
    try:
        _get_cgm(request).unpause_all_groups()
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error unpausing all groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Per-group routes
# ---------------------------------------------------------------------------

@camera_group_router.put(
    "/{group_id}",
    summary="Create or update a camera group",
    response_model=CameraGroupResponse,
)
async def put_camera_group(
    group_id: CameraGroupIdString,
    request: Request,
    body: CameraGroupCreateRequest = Body(..., examples=[CameraGroupCreateRequest.example()]),
) -> CameraGroupResponse:
    try:
        cgm = _get_cgm(request)
        camera_group = await cgm.create_or_update_camera_group(camera_configs=body.camera_configs)
        try:
            camera_group.state_machine.transition(CameraGroupStatus.CONNECTED)
            camera_group.state_machine.transition(CameraGroupStatus.STREAMING)
        except InvalidTransitionError as e:
            _handle_invalid_transition(e)
        return CameraGroupResponse(
            group_id=camera_group.id,
            camera_configs=camera_group.configs,
            status=camera_group.state_machine.phase.value,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating/updating camera group '{group_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.delete(
    "/{group_id}",
    summary="Disconnect and close a camera group",
    status_code=204,
)
async def delete_camera_group(group_id: CameraGroupIdString, request: Request) -> Response:
    try:
        cgm = _get_cgm(request)
        if group_id not in cgm.camera_groups:
            raise HTTPException(status_code=404, detail=f"Camera group '{group_id}' not found")
        cgm.camera_groups[group_id].state_machine.force_disconnect()
        await cgm.close_all_camera_groups()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing camera group '{group_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.post(
    "/{group_id}/recording",
    summary="Start recording for a camera group",
    status_code=201,
    response_model=StartRecordingResponse,
)
async def start_recording(
    group_id: CameraGroupIdString,
    request: Request,
    body: StartRecordingRequest = Body(default_factory=StartRecordingRequest),
) -> StartRecordingResponse:
    try:
        cgm = _get_cgm(request)
        if group_id not in cgm.camera_groups:
            raise HTTPException(status_code=404, detail=f"Camera group '{group_id}' not found")
        group = cgm.camera_groups[group_id]
        try:
            group.state_machine.transition(CameraGroupStatus.RECORDING)
        except InvalidTransitionError as e:
            _handle_invalid_transition(e)
        recording_info = _build_recording_info(body)
        await group.start_recording(recording_info=recording_info)
        return StartRecordingResponse(recording_id=recording_info.recording_uuid)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting recording for group '{group_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.delete(
    "/{group_id}/recording",
    summary="Stop recording for a camera group",
    response_model=StopRecordingResponse,
)
async def stop_recording(group_id: CameraGroupIdString, request: Request) -> StopRecordingResponse:
    try:
        cgm = _get_cgm(request)
        if group_id not in cgm.camera_groups:
            raise HTTPException(status_code=404, detail=f"Camera group '{group_id}' not found")
        group = cgm.camera_groups[group_id]
        recording_info, timestamp_stats = await group.stop_recording()
        try:
            group.state_machine.transition(CameraGroupStatus.STREAMING)
        except InvalidTransitionError as e:
            _handle_invalid_transition(e)
        return _build_stop_response([(recording_info, timestamp_stats)])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping recording for group '{group_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.post(
    "/{group_id}/pause",
    summary="Pause a camera group",
    status_code=204,
)
def pause_camera_group(group_id: CameraGroupIdString, request: Request) -> Response:
    try:
        cgm = _get_cgm(request)
        if group_id not in cgm.camera_groups:
            raise HTTPException(status_code=404, detail=f"Camera group '{group_id}' not found")
        cgm.camera_groups[group_id].pause()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing group '{group_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@camera_group_router.post(
    "/{group_id}/unpause",
    summary="Unpause a camera group",
    status_code=204,
)
def unpause_camera_group(group_id: CameraGroupIdString, request: Request) -> Response:
    try:
        cgm = _get_cgm(request)
        if group_id not in cgm.camera_groups:
            raise HTTPException(status_code=404, detail=f"Camera group '{group_id}' not found")
        cgm.camera_groups[group_id].unpause()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unpausing group '{group_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
