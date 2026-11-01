"""Keep the application's manager stable while choosing a new group's engine."""
from typing import Literal
import asyncio
import logging
import sys
from skellycam.core.camera.config.camera_config import MAX_MANUAL_EXPOSURE

from skellycam.core.camera_group.tasks.recommend_exposure import recommend_exposure

from skellycam.core.camera_group.rust_camera_group import RustCameraGroupManager
from skellycam.core.camera_group.camera_errors import CameraStateConflict

CameraBackend = Literal["python", "rust"]
logger = logging.getLogger(__name__)


class CameraBackendInUseError(ValueError):
    """A new engine was requested while the existing engine owns cameras."""


class CameraBackendManager:
    def __init__(self, *, global_kill_flag, worker_registry):
        from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
        self._arguments = dict(global_kill_flag=global_kill_flag, worker_registry=worker_registry)
        self._manager = CameraGroupManager(**self._arguments)
        self.backend: CameraBackend = "python"
        self._configuration_lock = asyncio.Lock()
        self._recording_requested = False

    async def create_or_update_camera_group(self, camera_configs, backend: CameraBackend = "python"):
        async with self._configuration_lock:
            return await self._create_or_update(camera_configs, backend)

    async def _create_or_update(self, camera_configs, backend):
        if backend != self.backend:
            if self._manager.camera_groups:
                raise CameraBackendInUseError("Close the current cameras before choosing another camera backend")
            from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
            implementation = CameraGroupManager if backend == "python" else RustCameraGroupManager
            self._manager = implementation(**self._arguments)
            self.backend = backend
        selected = {key for key, config in camera_configs.items()
                    if config.exposure_mode == "RECOMMEND" and config.use_this_camera}
        configs = {key: config.model_copy(deep=True) for key, config in camera_configs.items()}
        for key in selected:
            # Preserve the existing Linux device-auto policy: log2 exposure
            # candidates are not V4L2 absolute exposure units.
            configs[key].exposure_mode = "AUTO" if sys.platform == "linux" else "MANUAL"
        for key, config in configs.items():
            if config.use_this_camera and config.exposure_mode == "MANUAL" and config.exposure > MAX_MANUAL_EXPOSURE:
                logger.warning("Camera %s: limiting requested manual exposure %s to %s",
                               key, config.exposure, MAX_MANUAL_EXPOSURE)
                config.exposure = MAX_MANUAL_EXPOSURE
        group = await self._manager.create_or_update_camera_group(configs)
        if selected and sys.platform != "linux":
            await recommend_exposure(group, selected)
        return group

    @property
    def camera_groups(self):
        return self._manager.camera_groups

    @property
    def closing(self):
        return self._manager.closing

    def get_camera_group(self, camera_group_id):
        return self._manager.get_camera_group(camera_group_id)

    async def close_all_camera_groups(self):
        async with self._configuration_lock:
            await self._manager.close_all_camera_groups()
            self._recording_requested = False

    async def start_recording_all_groups(self, recording_info):
        async with self._configuration_lock:
            if self._recording_requested:
                raise CameraStateConflict('Recording is already running or starting')
            if not self.camera_groups:
                raise CameraStateConflict('No open cameras to record')
            # Reserve before awaiting: worker recording flags can lag the request.
            # A failed start must be stopped/closed before another can overwrite it.
            self._recording_requested = True
            await self._manager.start_recording_all_groups(recording_info)

    async def stop_recording_all_groups(self):
        async with self._configuration_lock:
            if not self._recording_requested:
                raise CameraStateConflict('No recording is running')
            result = await self._manager.stop_recording_all_groups()
            self._recording_requested = False
            return result

    def get_latest_frontend_payloads(self, if_newer_than, display_image_sizes=None):
        return self._manager.get_latest_frontend_payloads(if_newer_than, display_image_sizes)

    def get_backend_framerate_updates(self):
        return self._manager.get_backend_framerate_updates()

    def get_latest_performance_data(self, session_start_perf_ns):
        return self._manager.get_latest_performance_data(session_start_perf_ns)

    def pause_all_groups(self, await_paused=True):
        self._manager.pause_all_groups(await_paused)

    def unpause_all_groups(self, await_unpaused=True):
        self._manager.unpause_all_groups(await_unpaused)

    async def set_paused_all_groups(self, *, paused: bool, await_state_change: bool = True) -> None:
        await self._manager.set_paused_all_groups(paused=paused, await_state_change=await_state_change)

    async def pause_unpause_all_groups(self, await_state_change=True):
        await self._manager.pause_unpause_all_groups(await_state_change)

    def find_camera_group_by_camera_ids(self, camera_ids):
        return self._manager.find_camera_group_by_camera_ids(camera_ids)

    def to_state_dict(self):
        state = self._manager.to_state_dict()
        for group in state["camera_groups"].values():
            group["backend"] = self.backend
        return state
