import logging
import multiprocessing
from multiprocessing.sharedctypes import Synchronized
from dataclasses import dataclass, field

import numpy as np
from fastapi import FastAPI

from skellycam.api.websocket.performance_data import extract_performance_data_from_frames
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup, CameraGroupState
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import FramerateMessage
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import (
    CameraGroupIdString,
    CameraIdString,
    FrameNumberInt,
    MultiframeTimestampFloat,
    TopicSubscriptionQueue,
)
from skellycam.core.timestamps.recording_timestamp_stats import RecordingTimestampsStats

logger = logging.getLogger(__name__)

import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping

class RustCameraGroup:
    """Lightweight adapter wrapping a Rust camera group, exposing the same
    interface as ``CameraGroup`` for WebSocket and HTTP route compatibility."""

    def __init__(self, group_id: str, configs: CameraConfigs, native_manager):
        self._group_id = group_id
        self._configs = configs
        self._native = native_manager
        self._closed = False
        self._audio_recorder = None
        self._recording_info = None
        self._timebase = TimebaseMapping()

    @property
    def id(self) -> CameraGroupIdString:
        return self._group_id

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self._configs.keys())

    @property
    def configs(self) -> CameraConfigs:
        return self._configs

    @property
    def cameras(self):
        return SimpleNamespace(all_ready=not self._closed and self.id in self._native.list_groups())

    def get_latest_frontend_payload(
        self,
        if_newer_than: int,
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> tuple[FrameNumberInt, MultiframeTimestampFloat, memoryview] | None:
        payloads = self._native.get_latest_frame_payloads(if_newer_than=if_newer_than)
        group_data = payloads.get(self._group_id)
        if group_data is None:
            return None
        frame_number, timestamp_ns, py_bytes = group_data
        return (int(frame_number), float(timestamp_ns), memoryview(py_bytes))

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        if self._closed:
            return
        try:
            if self._recording_info is not None:
                await self.stop_recording()
        finally:
            await asyncio.to_thread(self._native.close_group, self.id)
            self._closed = True

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def update_camera_settings(self, requested_configs):
        requested_configs = {key: config for key, config in requested_configs.items() if config.use_this_camera}
        if not requested_configs:
            raise ValueError('Select at least one camera; close the group to disconnect all cameras')
        configs_dict = {}
        for camera_id, config in requested_configs.items():
            resolution = config.resolution
            configs_dict[camera_id] = {
                "camera_id": camera_id,
                "camera_index": config.camera_index,
                "width": resolution.width,
                "height": resolution.height,
                "exposure": config.exposure,
                "exposure_mode": config.exposure_mode,
                "framerate": config.framerate,
                "rotation": config.rotation.value,
            }
        await asyncio.to_thread(self._native.apply_configs, self._group_id, configs_dict)
        self._configs = requested_configs
        logger.info(f"Applied config updates for group {self._group_id}")
        return self._configs

    async def start_recording(self, recording_info):
        if not isinstance(recording_info, RecordingInfo):
            raise TypeError(f"Expected RecordingInfo, got {type(recording_info)}")
        if self._recording_info is not None:
            raise RuntimeError("This camera group is already recording")
        try:
            if recording_info.mic_device_index >= 0:
                import sounddevice
                import _skellycam_rust
                self._audio_recorder = await asyncio.to_thread(
                    _skellycam_rust.AudioRecorder, sounddevice._libname,
                    recording_info.audio_file_path, recording_info.mic_device_index,
                    json.dumps(asdict(self._timebase)),
                )
            await asyncio.to_thread(
                self._native.start_group_recording, self.id,
                recording_info.recording_directory, recording_info.recording_name,
            )
        except BaseException:
            if self._audio_recorder is not None:
                recorder, self._audio_recorder = self._audio_recorder, None
                await asyncio.to_thread(recorder.stop)
            raise
        self._recording_info = recording_info

    async def stop_recording(self) -> tuple["RecordingInfo", RecordingTimestampsStats]:
        """Stop recording for this group and return (RecordingInfo, stats)."""
        if self._recording_info is None:
            raise RuntimeError("This camera group is not recording")
        info, self._recording_info = self._recording_info, None
        try:
            group_data = await asyncio.to_thread(self._native.stop_group_recording, self.id)
        finally:
            if self._audio_recorder is not None:
                recorder, self._audio_recorder = self._audio_recorder, None
                await asyncio.to_thread(recorder.stop)
        if not group_data.get("video_paths") or not group_data.get("total_frames_per_camera"):
            raise RuntimeError("Rust recorder did not produce video frames")
        from skellycam.core.camera_group.rust_recording import finalize_native_recording
        stats = await finalize_native_recording(
            summary=group_data, recording_info=info,
            camera_configs=self.configs, timebase=self._timebase,
        )
        return info, stats

    async def pause_unpause(self, await_state_change=True):
        # Toggle: check current state from the native manager
        state = self._native.to_state_dict()
        groups = state.get("camera_groups", {})
        group_data = groups.get(self._group_id, {})
        cameras = group_data.get("cameras", [])
        is_paused = any(cam.get("is_paused", False) for cam in cameras) if cameras else False
        if is_paused:
            self.unpause()
        else:
            self.pause()

    def pause(self, await_paused=True):
        self._native.pause_group(self.id, True)

    def unpause(self, await_unpaused=True):
        self._native.pause_group(self.id, False)

    def get_latest_frames(self, if_newer_than=None, frame_buffers=None):
        import cv2
        from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
        native_frames = self._native.get_latest_raw_frames().get(self.id, {})
        if not native_frames:
            return None
        if if_newer_than is not None and all(source['frame_number'] <= if_newer_than for source in native_frames.values()):
            return None
        result = {}
        for camera_id, source in native_frames.items():
            image = cv2.imdecode(np.frombuffer(source["jpeg_bytes"], dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"Cannot decode native frame for camera {camera_id}")
            config = self.configs[camera_id]
            rotation = config.rotation.value
            # The native dispatcher caches JPEGs AFTER applying display rotation.
            # Python frame records hold sensor-oriented pixels plus a rotation to
            # apply later (tracking, preview, recording). Restore that contract
            # directly into the caller-owned array, without another image allocation.
            image_shape = image.shape
            inverse_rotation = rotation
            if rotation == cv2.ROTATE_90_CLOCKWISE:
                inverse_rotation = cv2.ROTATE_90_COUNTERCLOCKWISE
                image_shape = (image.shape[1], image.shape[0], image.shape[2])
            elif rotation == cv2.ROTATE_90_COUNTERCLOCKWISE:
                inverse_rotation = cv2.ROTATE_90_CLOCKWISE
                image_shape = (image.shape[1], image.shape[0], image.shape[2])
            frame_dtype = np.dtype([
                ("frame_metadata", FRAME_METADATA_DTYPE), ("image", np.uint8, image_shape),
            ], align=True)
            frame = None if frame_buffers is None else frame_buffers.get(camera_id)
            if frame is None or frame.dtype != frame_dtype:
                frame = np.zeros(1, dtype=frame_dtype).view(np.recarray)
                if frame_buffers is not None:
                    frame_buffers[camera_id] = frame
            if rotation == -1:
                frame.image[0] = image
            else:
                cv2.rotate(src=image, rotateCode=inverse_rotation, dst=frame.image[0])
            metadata = frame.frame_metadata
            metadata.camera_info.camera_id = camera_id
            metadata.camera_info.camera_index = config.camera_index
            metadata.camera_info.rotation = config.rotation.value
            metadata.camera_info.color_channels = config.color_channels
            metadata.frame_number = source["frame_number"]
            metadata.timebase_mapping = self._timebase.to_numpy_record_array()
            times = source["timestamps"]
            metadata.timestamps.initialized_ns = times["loop_start_ns"]
            metadata.timestamps.pre_frame_grab_ns = times["loop_start_ns"]
            metadata.timestamps.post_frame_grab_ns = times["frame_available_ns"]
            metadata.timestamps.pre_frame_retrieve_ns = times["frame_available_ns"]
            metadata.timestamps.post_frame_retrieve_ns = times["post_jpeg_extract_ns"]
            metadata.timestamps.pre_copy_to_camera_shm_ns = times["pre_send_ns"]
            metadata.timestamps.post_copy_to_camera_shm_ns = times["gatherer_received_ns"]
            result[camera_id] = frame
        return result

    def get_frontend_payload_by_frame_number(self, frame_number, display_image_sizes=None):
        latest = self.get_latest_frontend_payload(frame_number - 1, display_image_sizes)
        if latest is None or latest[0] != frame_number:
            return None
        return latest[2], latest[1]

    def to_state(self) -> CameraGroupState:
        from skellycam.core.camera.camera_worker import CameraState
        state = self._native.to_state_dict()
        groups = state.get("camera_groups", {})
        group_data = groups.get(self._group_id, {})
        cameras_data = group_data.get("cameras", [])
        cameras_state = {}
        for cam in cameras_data:
            cameras_state[cam["unique_identifier"]] = CameraState(
                pid=-1,
                name=cam.get("display_name", "Unknown"),
                alive=not self._closed,
                status={
                    "connected": not self._closed,
                    "closed": self._closed,
                    "recording_in_progress": cam.get("is_recording", False),
                    "is_paused": cam.get("is_paused", False),
                    "error": False,
                },
            )
        return CameraGroupState(
            id=self._group_id,
            configs=self._configs,
            cameras=cameras_state,
            alive=not self._closed,
            recording_in_progress=self._recording_info is not None,
            paused=bool(cameras_data) and all(camera.get("is_paused", False) for camera in cameras_data),
        )


@dataclass
class RustCameraGroupManager:
    """Camera-group implementation backed by native Rust capture workers."""

    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    closing: bool = False
    camera_groups: dict[CameraGroupIdString, RustCameraGroup] = field(default_factory=dict)
    camera_group_framerate_subscriptions: dict[CameraGroupIdString, TopicSubscriptionQueue] = field(
        default_factory=dict
    )

    def __post_init__(self):
        import _skellycam_rust
        import imageio_ffmpeg
        # The platform wheel supplies the executable; PyInstaller collects it.
        # See [@imageioFfmpegExecutable] in references.bib.
        _skellycam_rust.configure_ffmpeg(imageio_ffmpeg.get_ffmpeg_exe())
        self._native = _skellycam_rust.CameraGroupManager()
        # Per-group framerate tracking: (frame_number, timestamp_ns) pairs
        self._framerate_timestamps: dict[CameraGroupIdString, list[tuple[int, float]]] = {}

    async def create_and_start_camera_group(self, camera_configs: CameraConfigs) -> RustCameraGroup:
        configs_dict: dict[str, dict] = {}
        for camera_id, config in camera_configs.items():
            configs_dict[camera_id] = {
                "camera_id": camera_id,
                "camera_index": config.camera_index,
                "width": config.resolution.width,
                "height": config.resolution.height,
                "exposure": config.exposure,
                "exposure_mode": config.exposure_mode,
                "framerate": config.framerate,
                "rotation": config.rotation.value,
            }
        group_id = await asyncio.to_thread(self._native.create_or_update_group, configs_dict)
        group = RustCameraGroup(
            group_id=group_id,
            configs=camera_configs,
            native_manager=self._native,
        )
        self.camera_groups[group_id] = group
        logger.info(
            f"Created Rust camera group {group_id} "
            f"with cameras: {list(camera_configs.keys())}"
        )
        return group

    async def create_or_update_camera_group(self, camera_configs: CameraConfigs) -> RustCameraGroup:
        matches = self._get_configs_by_group(camera_configs)
        if not matches:
            return await self.create_and_start_camera_group(camera_configs)
        if len(matches) > 1:
            raise ValueError("Cannot update multiple camera groups at once")
        group = self.get_camera_group(next(iter(matches)))
        await group.update_camera_settings(camera_configs)
        return group

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> RustCameraGroup:
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        return self.camera_groups[camera_group_id]

    def _get_configs_by_group(
        self, camera_configs: CameraConfigs
    ) -> dict[CameraGroupIdString, CameraConfigs]:
        return {
            group.id: {key: value for key, value in camera_configs.items() if key in group.camera_ids}
            for group in self.camera_groups.values()
            if set(camera_configs).intersection(group.camera_ids)
        }

    async def close_all_camera_groups(self) -> None:
        self.closing = True
        errors = []
        try:
            for group in list(self.camera_groups.values()):
                try:
                    await group.close()
                except Exception as error:
                    errors.append(error)
            self.camera_groups.clear()
            self._framerate_timestamps.clear()
        finally:
            self.closing = False
        if errors:
            raise ExceptionGroup("Rust camera group shutdown failed", errors)

    async def start_recording_all_groups(self, recording_info: RecordingInfo) -> None:
        started = []
        try:
            for group in self.camera_groups.values():
                # One microphone recording per recording session, even when
                # the session contains multiple independent camera groups.
                group_info = recording_info if not started else recording_info.model_copy(update={"mic_device_index": -1})
                await group.start_recording(group_info)
                started.append(group)
        except BaseException:
            for group in started:
                await group.stop_recording()
            raise
        logger.info(f"Started recording for all Rust camera groups → {recording_info.recording_directory}")

    async def stop_recording_all_groups(self) -> list[tuple["RecordingInfo", "RecordingTimestampsStats"]]:
        results, errors = [], []
        for group in self.camera_groups.values():
            try:
                results.append(await group.stop_recording())
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("Rust recording finalization failed", errors)
        return results

    def get_latest_frontend_payloads(
        self,
        if_newer_than: dict[CameraGroupIdString, int],
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> dict[CameraGroupIdString, tuple[FrameNumberInt, MultiframeTimestampFloat, memoryview]]:
        if self.closing or not self.camera_groups:
            return {}
        threshold = min((if_newer_than.get(key, -1) for key in self.camera_groups), default=-1)
        raw = self._native.get_latest_frame_payloads(if_newer_than=threshold)
        result: dict[CameraGroupIdString, tuple[
            FrameNumberInt, MultiframeTimestampFloat, memoryview
        ]] = {}
        for group_id, (frame_number, timestamp_ns, py_bytes) in raw.items():
            if frame_number <= if_newer_than.get(group_id, -1):
                continue
            result[group_id] = (int(frame_number), float(timestamp_ns), memoryview(py_bytes))
            # Track for framerate calculations (keep last 300 samples)
            if group_id not in self._framerate_timestamps:
                self._framerate_timestamps[group_id] = []
            ts_list = self._framerate_timestamps[group_id]
            ts_list.append((int(frame_number), float(timestamp_ns)))
            if len(ts_list) > 300:
                ts_list.pop(0)
        return result

    def get_backend_framerate_updates(self) -> dict[CameraGroupIdString, CurrentFramerate]:
        result: dict[CameraGroupIdString, CurrentFramerate] = {}
        for group_id, ts_list in self._framerate_timestamps.items():
            if len(ts_list) < 2:
                continue
            # Compute from frame_number deltas and timestamp deltas
            first_fn, first_ts = ts_list[0]
            last_fn, last_ts = ts_list[-1]
            frame_delta = last_fn - first_fn
            time_delta_ns = last_ts - first_ts
            if frame_delta > 0 and time_delta_ns > 0:
                samples = np.asarray(ts_list, dtype=np.float64)
                durations_ms = np.diff(samples[:, 1]) / np.diff(samples[:, 0]) / 1_000_000.0
                result[group_id] = CurrentFramerate.from_durations_ms(
                    durations_ms=durations_ms, framerate_source="Rust Backend",
                )
        return result

    def get_latest_performance_data(
        self, session_start_perf_ns: int,
    ) -> dict[CameraGroupIdString, dict]:
        result = {}
        for group in self.camera_groups.values():
            frames = group.get_latest_frames()
            if frames:
                result[group.id] = extract_performance_data_from_frames(
                    latest_frames=frames, session_start_perf_ns=session_start_perf_ns,
                )
        return result

    def pause_all_groups(self, await_paused: bool = True) -> None:
        self._native.pause()
        logger.info("Paused all Rust camera groups")

    async def set_paused_all_groups(self, *, paused: bool, await_state_change: bool = True) -> None:
        if paused:
            self._native.pause()
        else:
            self._native.unpause()

    async def pause_unpause_all_groups(self, await_state_change: bool = True) -> None:
        # Toggle: check if any camera is paused
        state = self._native.to_state_dict()
        any_paused = False
        for group_data in state.get("camera_groups", {}).values():
            for cam in group_data.get("cameras", []):
                if cam.get("is_paused", False):
                    any_paused = True
                    break
        if any_paused:
            self._native.unpause()
            logger.info("Unpaused all Rust camera groups")
        else:
            self._native.pause()
            logger.info("Paused all Rust camera groups")

    def unpause_all_groups(self, await_unpaused: bool = True) -> None:
        self._native.unpause()
        logger.info("Unpaused all Rust camera groups")

    def find_camera_group_by_camera_ids(
        self, camera_ids: list[CameraIdString],
    ) -> RustCameraGroup | None:
        for group in self.camera_groups.values():
            if all(cam_id in group.camera_ids for cam_id in camera_ids):
                return group
        return None

    def to_state_dict(self) -> dict[CameraGroupIdString, dict]:
        return {
            "camera_groups": {
                cg_id: cg.to_state().model_dump()
                for cg_id, cg in self.camera_groups.items()
            }
        }
