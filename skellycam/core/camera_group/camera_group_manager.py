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
        timestamp_s = float(timestamp_ns) / 1_000_000_000.0
        return (int(frame_number), timestamp_s, bytearray(py_bytes))

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        self._native.close_all_groups()

    # ── Stubs for unimplemented functionality ────────────────────────────

    async def update_camera_settings(self, requested_configs):
        raise NotImplementedError("Config updates not yet in Rust backend")

    async def start_recording(self, recording_info):
        raise NotImplementedError("Recording not yet in Rust backend")

    async def stop_recording(self):
        raise NotImplementedError("Recording not yet in Rust backend")

    async def pause_unpause(self, await_state_change=True):
        raise NotImplementedError("Pause not yet in Rust backend")

    def pause(self, await_paused=True):
        raise NotImplementedError("Pause not yet in Rust backend")

    def unpause(self, await_unpaused=True):
        raise NotImplementedError("Pause not yet in Rust backend")

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
                    "connected": True, "closed": False,
                    "recording_in_progress": False, "is_paused": False, "error": False,
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

    async def create_and_start_camera_group(self, camera_configs: CameraConfigs) -> RustCameraGroup:
        return await self.create_or_update_camera_group(camera_configs)

    async def create_or_update_camera_group(self, camera_configs: CameraConfigs) -> RustCameraGroup:
        configs_dict: dict[str, dict] = {}
        for camera_id, config in camera_configs.items():
            resolution = config.resolution
            configs_dict[camera_id] = {
                "camera_index": config.camera_index,
                "width": resolution.width,
                "height": resolution.height,
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
        logger.success("Closed all Rust camera groups")
        self.closing = False

    async def start_recording_all_groups(self, recording_info: RecordingInfo) -> None:
        raise NotImplementedError("Recording not yet in Rust backend")

    async def stop_recording_all_groups(self) -> list[tuple[RecordingInfo, "RecordingTimestampsStats"]]:
        raise NotImplementedError("Recording not yet in Rust backend")

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
            timestamp_s = float(timestamp_ns) / 1_000_000_000.0
            result[group_id] = (int(frame_number), timestamp_s, bytearray(py_bytes))
        return result

    def get_backend_framerate_updates(self) -> dict[CameraGroupIdString, CurrentFramerate]:
        return {}

    def get_latest_performance_data(
        self, session_start_perf_ns: int,
    ) -> dict[CameraGroupIdString, dict]:
        return {}

    def pause_all_groups(self, await_paused: bool = True) -> None:
        raise NotImplementedError("Pause not yet in Rust backend")

    async def pause_unpause_all_groups(self, await_state_change: bool = True) -> None:
        raise NotImplementedError("Pause not yet in Rust backend")

    def unpause_all_groups(self, await_unpaused: bool = True) -> None:
        raise NotImplementedError("Pause not yet in Rust backend")

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
