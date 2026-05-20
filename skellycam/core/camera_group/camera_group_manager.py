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

# ── Backend selector ────────────────────────────────────────────────────────
# True  → Rust openpnp-capture engine (PyO3)
# False → Python OpenCV multiprocessing engine (original)
USE_RUST_BACKEND: bool = True


@dataclass
class CameraGroupManager:
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    closing: bool = False
    camera_groups: dict[CameraGroupIdString, CameraGroup] = field(default_factory=dict)
    camera_group_framerate_subscriptions: dict[CameraGroupIdString, TopicSubscriptionQueue] = field(
        default_factory=dict
    )

    async def create_and_start_camera_group(self, camera_configs: CameraConfigs) -> CameraGroup:
        """Create a camera group with the provided configuration settings."""
        camera_group = CameraGroup.create(
            camera_configs=camera_configs,
            heartbeat_timestamp=self.worker_registry.heartbeat_timestamp,
            global_kill_flag=self.global_kill_flag,
            worker_registry=self.worker_registry,
        )
        self.camera_group_framerate_subscriptions[camera_group.id] = (
            camera_group.ipc.pubsub.get_subscription(TopicTypes.FRAMERATE)
        )
        self.camera_groups[camera_group.id] = camera_group
        await self.camera_groups[camera_group.id].start()

        logger.info(
            f"Creating camera group with ID: {camera_group.id} "
            f"and cameras: {camera_group.camera_ids}"
        )
        return camera_group

    async def create_or_update_camera_group(self, camera_configs: CameraConfigs) -> CameraGroup:
        """Create a camera group with the provided configuration settings."""
        camera_groups = self._get_configs_by_group(camera_configs)
        if not camera_groups:
            return await self.create_and_start_camera_group(camera_configs)
        if len(camera_groups) > 1:
            raise NotImplementedError("Cannot update multiple camera groups at once (yet).")
        camera_group_id, configs = next(iter(camera_groups.items()))
        camera_group = self.get_camera_group(camera_group_id)
        await camera_group.update_camera_settings(requested_configs=configs)
        return camera_group

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> CameraGroup:
        """Retrieve a camera group by its ID."""
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        return self.camera_groups[camera_group_id]

    def _get_configs_by_group(
        self, camera_configs: CameraConfigs
    ) -> dict[CameraGroupIdString, CameraConfigs]:
        configs_by_group: dict[CameraGroupIdString, CameraConfigs] = {}
        for camera_group in self.camera_groups.values():
            configs_by_group[camera_group.id] = {}
            for camera_id, camera_config in camera_configs.items():
                if camera_id in camera_group.camera_ids:
                    configs_by_group[camera_group.id][camera_id] = camera_config
        return configs_by_group

    async def close_all_camera_groups(self) -> None:
        """Close all camera groups."""
        self.closing = True
        if not self.camera_groups:
            logger.warning("No camera groups to close.")
            return

        for camera_group_id in list(self.camera_groups.keys()):
            await self.camera_groups[camera_group_id].close()
        logger.success(
            f"Successfully closed all camera groups ids - {list(self.camera_groups.keys())}"
        )
        self.camera_groups.clear()
        self.closing = False

    async def start_recording_all_groups(self, recording_info: RecordingInfo) -> None:
        """Start recording for all camera groups."""
        for camera_group in self.camera_groups.values():
            await camera_group.start_recording(recording_info=recording_info)
            logger.info(f"Started recording for camera group ID: {camera_group.id}")

    async def stop_recording_all_groups(self) -> list[tuple["RecordingInfo", "RecordingTimestampsStats"]]:
        """Stop recording for all camera groups."""
        results: list[tuple[RecordingInfo, RecordingTimestampsStats]] = []
        for camera_group in self.camera_groups.values():
            results.append(await camera_group.stop_recording())
            logger.info(f"Stopped recording for camera group ID: {camera_group.id}")
        return results

    def get_latest_frontend_payloads(
        self,
        if_newer_than: int,
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> dict[CameraGroupIdString, tuple[FrameNumberInt, MultiframeTimestampFloat, bytearray]]:
        if self.closing:
            return {}
        fe_payloads: dict[
            CameraGroupIdString, tuple[FrameNumberInt, MultiframeTimestampFloat, bytearray]
        ] = {}
        for camera_group in self.camera_groups.values():
            fe_return = camera_group.get_latest_frontend_payload(
                if_newer_than=if_newer_than,
                display_image_sizes=display_image_sizes,
            )
            if fe_return is None:
                continue
            frame_number, multiframe_timestamp, fe_payload = fe_return
            if fe_payload is None:
                continue
            fe_payloads[camera_group.id] = (frame_number, multiframe_timestamp, fe_payload)
        return fe_payloads

    def get_backend_framerate_updates(self) -> dict[CameraGroupIdString, CurrentFramerate]:
        """Get the latest framerate updates for all camera groups."""
        framerate_updates: dict[CameraGroupIdString, CurrentFramerate] = {}
        for camera_group_id, subscription in self.camera_group_framerate_subscriptions.items():
            if not subscription.empty():
                framerate_update = subscription.get()
                if isinstance(framerate_update, FramerateMessage):
                    framerate_updates[camera_group_id] = framerate_update.current_framerate
                else:
                    raise TypeError(
                        f"Received unexpected data type from framerate subscription: "
                        f"{type(framerate_update)}"
                    )
        return framerate_updates

    def get_latest_performance_data(
        self,
        session_start_perf_ns: int,
    ) -> dict[CameraGroupIdString, dict]:
        """
        Get per-camera frame lifecycle performance data for all camera groups.
        Returns a dict mapping camera_group_id to performance data dicts
        suitable for streaming to the frontend Perspective tables.
        """
        if self.closing:
            return {}
        result: dict[CameraGroupIdString, dict] = {}
        for camera_group in self.camera_groups.values():
            latest_frames = camera_group.get_latest_frames()
            if latest_frames is None:
                continue
            try:
                perf_data = extract_performance_data_from_frames(
                    latest_frames=latest_frames,
                    session_start_perf_ns=session_start_perf_ns,
                )
                result[camera_group.id] = perf_data
            except Exception as e:
                logger.debug(f"Error extracting performance data for group {camera_group.id}: {e}")
        return result

    def pause_all_groups(self, await_paused: bool = True) -> None:
        """Pause all camera groups."""
        for camera_group in self.camera_groups.values():
            camera_group.pause(await_paused=await_paused)
            logger.info(f"Paused camera group ID: {camera_group.id}")

    async def pause_unpause_all_groups(self, await_state_change: bool = True) -> None:
        """Pause/Unpause all camera groups."""
        for camera_group in self.camera_groups.values():
            await camera_group.pause_unpause(await_state_change=await_state_change)
            logger.info(f"Paused camera group ID: {camera_group.id}")

    def unpause_all_groups(self, await_unpaused: bool = True) -> None:
        """Unpause all camera groups."""
        for camera_group in self.camera_groups.values():
            camera_group.unpause(await_unpaused=await_unpaused)
            logger.info(f"Unpaused camera group ID: {camera_group.id}")

    def find_camera_group_by_camera_ids(
        self, camera_ids: list[CameraIdString]
    ) -> CameraGroup | None:
        """Find a camera group that contains all the specified camera IDs."""
        for camera_group in self.camera_groups.values():
            if all(camera_id in camera_group.camera_ids for camera_id in camera_ids):
                return camera_group
        return None

    def to_state_dict(self) -> dict[CameraGroupIdString, dict]:
        """Convert the CameraGroupManager to a serializable state dictionary."""
        return {
            "camera_groups": {
                cg_id: cg.to_state().model_dump() for cg_id, cg in self.camera_groups.items()
            }
        }


# ── Rust PyO3 adapter ──────────────────────────────────────────────────────


@dataclass
class _RustStatsAdapter:
    """Lightweight adapter mimicking numpy recarray fields consumed by the
    stop-recording HTTP route's ``_stats_summary()`` helper.

    Mirrors the attribute interface of the numpy recarrays produced by
    ``calculate_statistics()`` — specifically ``median_value``, ``mean_value``,
    ``standard_deviation_value``, ``min_value``, and ``max_value``.
    """
    median_value: float
    mean_value: float
    standard_deviation_value: float
    min_value: float
    max_value: float


@dataclass
class _RustRecordingTimestampsStats:
    """Return type adapter — same attribute names as ``RecordingTimestampsStats``
    so the stop-recording HTTP route can unpack it without branching on backend."""
    recording_info: "RecordingInfo"
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    framerate_stats: _RustStatsAdapter
    frame_duration_stats: _RustStatsAdapter
    inter_camera_grab_range_ms: _RustStatsAdapter


def _parse_rust_stats(stats_dict: dict | None) -> _RustStatsAdapter:
    """Convert a single ``StatsSummary`` dict (from JSON) to a _RustStatsAdapter.

    The Rust ``StatsSummary`` keys are: median, mean, std, min, max, cv_pct, n.
    We drop cv_pct and n since they are not in the Python stats interface.
    """
    if stats_dict is None:
        return _RustStatsAdapter(0.0, 0.0, 0.0, 0.0, 0.0)
    return _RustStatsAdapter(
        median_value=float(stats_dict.get("median", 0.0)),
        mean_value=float(stats_dict.get("mean", 0.0)),
        standard_deviation_value=float(stats_dict.get("std", 0.0)),
        min_value=float(stats_dict.get("min", 0.0)),
        max_value=float(stats_dict.get("max", 0.0)),
    )


def _convert_rust_recording_summary(
    summary: dict,
) -> tuple["RecordingInfo", _RustRecordingTimestampsStats]:
    """Parse a single Rust ``RecordingSummary`` dict into Python adapter objects.

    The Rust bridge returns a dict with keys:
        total_frames_per_camera, video_paths, csv_paths, info_json_path, stats_json
    """
    import json

    info_json_path = summary.get("info_json_path", "")
    recording_info = RecordingInfo(
        recording_name="unknown",
        recording_directory="",
    )
    if info_json_path:
        try:
            with open(info_json_path, "r") as f:
                info_data = json.load(f)
            rec_name = info_data.get("recording_directory", "unknown")
            recording_info = RecordingInfo(
                recording_name=rec_name,
                recording_directory=info_data.get("recording_directory", ""),
                mic_device_index=-1,
            )
        except (OSError, json.JSONDecodeError):
            pass

    stats_json = summary.get("stats_json")
    stats = {}
    if stats_json:
        try:
            stats = json.loads(stats_json)
        except json.JSONDecodeError:
            pass

    multiframe_fps = _parse_rust_stats(stats.get("multiframe_fps"))
    multiframe_duration_ns = stats.get("multiframe_duration_ns")
    frame_arrival_spread = stats.get("frame_arrival_spread")

    if multiframe_duration_ns:
        frame_duration = _RustStatsAdapter(
            median_value=float(multiframe_duration_ns.get("median", 0.0)) / 1_000_000.0,
            mean_value=float(multiframe_duration_ns.get("mean", 0.0)) / 1_000_000.0,
            standard_deviation_value=float(multiframe_duration_ns.get("std", 0.0)) / 1_000_000.0,
            min_value=float(multiframe_duration_ns.get("min", 0.0)) / 1_000_000.0,
            max_value=float(multiframe_duration_ns.get("max", 0.0)) / 1_000_000.0,
        )
        total_duration_sec = float(multiframe_duration_ns.get("mean", 0.0)) * stats.get("total_multiframes", 0) / 1_000_000_000.0
    else:
        frame_duration = _RustStatsAdapter(0.0, 0.0, 0.0, 0.0, 0.0)
        total_duration_sec = 0.0

    inter_camera_sync = _parse_rust_stats(frame_arrival_spread)
    if frame_arrival_spread:
        inter_camera_sync = _RustStatsAdapter(
            median_value=float(frame_arrival_spread.get("median", 0.0)) / 1_000_000.0,
            mean_value=float(frame_arrival_spread.get("mean", 0.0)) / 1_000_000.0,
            standard_deviation_value=float(frame_arrival_spread.get("std", 0.0)) / 1_000_000.0,
            min_value=float(frame_arrival_spread.get("min", 0.0)) / 1_000_000.0,
            max_value=float(frame_arrival_spread.get("max", 0.0)) / 1_000_000.0,
        )

    ts_stats = _RustRecordingTimestampsStats(
        recording_info=recording_info,
        number_of_cameras=len(summary.get("video_paths", [])),
        number_of_frames=int(summary.get("total_frames_per_camera", 0)),
        total_duration_sec=total_duration_sec,
        framerate_stats=multiframe_fps,
        frame_duration_stats=frame_duration,
        inter_camera_grab_range_ms=inter_camera_sync,
    )
    return recording_info, ts_stats


class RustCameraGroup:
    """Lightweight adapter wrapping a Rust camera group, exposing the same
    interface as ``CameraGroup`` for WebSocket and HTTP route compatibility."""

    def __init__(self, group_id: str, configs: CameraConfigs, native_manager):
        self._group_id = group_id
        self._configs = configs
        self._native = native_manager

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
        """Minimal adapter so ``cameras.all_ready`` returns True."""
        return _RustCameraManagerStub()

    def get_latest_frontend_payload(
        self,
        if_newer_than: int,
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> tuple[FrameNumberInt, MultiframeTimestampFloat, bytearray] | None:
        payloads = self._native.get_latest_frame_payloads(if_newer_than=if_newer_than)
        group_data = payloads.get(self._group_id)
        if group_data is None:
            return None
        frame_number, timestamp_ns, py_bytes = group_data
        return (int(frame_number), float(timestamp_ns), bytearray(py_bytes))

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        """Mark this group as closed. Actual Rust group shutdown is handled
        by ``RustCameraGroupManager.close_all_camera_groups()``."""
        pass

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def update_camera_settings(self, requested_configs):
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
        self._native.apply_configs(self._group_id, configs_dict)
        logger.info(f"Applied config updates for group {self._group_id}")

    async def start_recording(self, recording_info):
        from skellycam.core.recorders.videos.recording_info import RecordingInfo
        if isinstance(recording_info, RecordingInfo):
            self._native.start_recording(
                output_dir=recording_info.recording_directory,
                label=recording_info.recording_name,
            )
        else:
            raise TypeError(f"Expected RecordingInfo, got {type(recording_info)}")

    async def stop_recording(self) -> tuple["RecordingInfo", _RustRecordingTimestampsStats]:
        """Stop recording for this group and return (RecordingInfo, stats)."""
        raw_result = self._native.stop_recording()
        group_data = raw_result.get(self._group_id, {})
        return _convert_rust_recording_summary(group_data)

    async def pause_unpause(self, await_state_change=True):
        # Toggle: check current state from the native manager
        state = self._native.to_state_dict()
        groups = state.get("camera_groups", {})
        group_data = groups.get(self._group_id, {})
        cameras = group_data.get("cameras", [])
        is_paused = any(cam.get("is_paused", False) for cam in cameras) if cameras else False
        if is_paused:
            self._native.unpause()
        else:
            self._native.pause()

    def pause(self, await_paused=True):
        self._native.pause()

    def unpause(self, await_unpaused=True):
        self._native.unpause()

    def get_latest_frames(self):
        return None

    def get_frontend_payload_by_frame_number(self, frame_number, display_image_sizes=None):
        return None

    def to_state(self) -> CameraGroupState:
        from skellycam.core.camera.camera_worker import CameraState
        state = self._native.to_state_dict()
        groups = state.get("camera_groups", {})
        group_data = groups.get(self._group_id, {})
        cameras_data = group_data.get("cameras", [])
        cameras_state = {}
        for cam in cameras_data:
            cameras_state[str(cam["camera_index"])] = CameraState(
                pid=-1,
                name=cam.get("display_name", "Unknown"),
                alive=True,
                status={
                    "connected": True,
                    "closed": False,
                    "recording_in_progress": cam.get("is_recording", False),
                    "is_paused": cam.get("is_paused", False),
                    "error": False,
                },
            )
        return CameraGroupState(
            id=self._group_id,
            configs=self._configs,
            cameras=cameras_state,
            alive=True,
        )


class _RustCameraManagerStub:
    @property
    def all_ready(self) -> bool:
        return True


@dataclass
class RustCameraGroupManager:
    """Rust PyO3 backend — drop-in replacement for the Python multiprocessing
    ``CameraGroupManager`` when ``USE_RUST_BACKEND`` is ``True``."""

    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    closing: bool = False
    camera_groups: dict[CameraGroupIdString, RustCameraGroup] = field(default_factory=dict)
    camera_group_framerate_subscriptions: dict[CameraGroupIdString, TopicSubscriptionQueue] = field(
        default_factory=dict
    )

    def __post_init__(self):
        import _skellycam_rust
        self._native = _skellycam_rust.CameraGroupManager()
        # Per-group framerate tracking: (frame_number, timestamp_ns) pairs
        self._framerate_timestamps: dict[CameraGroupIdString, list[tuple[int, float]]] = {}

    async def create_and_start_camera_group(self, camera_configs: CameraConfigs) -> RustCameraGroup:
        return await self.create_or_update_camera_group(camera_configs)

    async def create_or_update_camera_group(self, camera_configs: CameraConfigs) -> RustCameraGroup:
        configs_dict: dict[str, dict] = {}
        for camera_id, config in camera_configs.items():
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
        group_id = self._native.create_or_update_group(configs_dict)
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

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> RustCameraGroup:
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        return self.camera_groups[camera_group_id]

    def _get_configs_by_group(
        self, camera_configs: CameraConfigs
    ) -> dict[CameraGroupIdString, CameraConfigs]:
        return {}

    async def close_all_camera_groups(self) -> None:
        self.closing = True
        if not self.camera_groups:
            return
        self._native.close_all_groups()
        self.camera_groups.clear()
        self._framerate_timestamps.clear()
        logger.success("Closed all Rust camera groups")
        self.closing = False

    async def start_recording_all_groups(self, recording_info: RecordingInfo) -> None:
        self._native.start_recording(
            output_dir=recording_info.recording_directory,
            label=recording_info.recording_name,
        )
        logger.info(f"Started recording for all Rust camera groups → {recording_info.recording_directory}")

    async def stop_recording_all_groups(self) -> list[tuple["RecordingInfo", "RecordingTimestampsStats"]]:
        import json
        raw_result = self._native.stop_recording()
        logger.info(f"Stopped recording for {len(raw_result)} Rust camera group(s)")

        results: list[tuple[RecordingInfo, _RustRecordingTimestampsStats]] = []
        for group_id, summary in raw_result.items():
            recording_info, ts_stats = _convert_rust_recording_summary(summary)
            results.append((recording_info, ts_stats))

        return results

    def get_latest_frontend_payloads(
        self,
        if_newer_than: int,
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> dict[CameraGroupIdString, tuple[FrameNumberInt, MultiframeTimestampFloat, bytearray]]:
        if self.closing or not self.camera_groups:
            return {}
        raw = self._native.get_latest_frame_payloads(if_newer_than=if_newer_than)
        result: dict[CameraGroupIdString, tuple[
            FrameNumberInt, MultiframeTimestampFloat, bytearray
        ]] = {}
        for group_id, (frame_number, timestamp_ns, py_bytes) in raw.items():
            result[group_id] = (int(frame_number), float(timestamp_ns), bytearray(py_bytes))
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
                fps = frame_delta / (time_delta_ns / 1_000_000_000.0)
                mean_duration_ms = (time_delta_ns / frame_delta) / 1_000_000.0
                result[group_id] = CurrentFramerate(
                    mean_frame_duration_ms=mean_duration_ms,
                    mean_frames_per_second=fps,
                    frame_duration_stddev=0.0,
                    frame_duration_median=mean_duration_ms,
                    calculation_window_size=len(ts_list),
                    framerate_source="Rust Backend",
                )
        return result

    def get_latest_performance_data(
        self, session_start_perf_ns: int,
    ) -> dict[CameraGroupIdString, dict]:
        import json
        snapshot_json = self._native.get_performance_snapshot()
        if snapshot_json is None:
            return {}
        try:
            snapshot = json.loads(snapshot_json)
            # Return under the first group's ID (or use a synthetic key)
            if self.camera_groups:
                group_id = next(iter(self.camera_groups.keys()))
                return {group_id: snapshot}
        except (json.JSONDecodeError, StopIteration):
            pass
        return {}

    def pause_all_groups(self, await_paused: bool = True) -> None:
        self._native.pause()
        logger.info("Paused all Rust camera groups")

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


# ── Singleton factory ───────────────────────────────────────────────────────

_CAMERA_GROUP_MANAGER: CameraGroupManager | RustCameraGroupManager | None = None


def get_or_create_camera_group_manager(
    app: FastAPI,
) -> CameraGroupManager | RustCameraGroupManager:
    """Create the singleton CameraGroupManager instance.

    Reads ``USE_RUST_BACKEND`` from this module to select between the
    original Python multiprocessing backend and the Rust PyO3 backend.
    """
    global _CAMERA_GROUP_MANAGER

    if _CAMERA_GROUP_MANAGER is not None:
        return _CAMERA_GROUP_MANAGER

    if USE_RUST_BACKEND:
        _CAMERA_GROUP_MANAGER = RustCameraGroupManager(
            global_kill_flag=app.state.global_kill_flag,
            worker_registry=app.state.worker_registry,
        )
    else:
        _CAMERA_GROUP_MANAGER = CameraGroupManager(
            global_kill_flag=app.state.global_kill_flag,
            worker_registry=app.state.worker_registry,
        )
    return _CAMERA_GROUP_MANAGER
