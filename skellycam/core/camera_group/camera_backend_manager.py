"""Keep the application's manager stable while choosing a new group's engine."""
from typing import Literal

from skellycam.core.camera_group.rust_camera_group import RustCameraGroupManager

CameraBackend = Literal["python", "rust"]


class CameraBackendInUseError(ValueError):
    """A new engine was requested while the existing engine owns cameras."""


class CameraBackendManager:
    def __init__(self, *, global_kill_flag, worker_registry):
        from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
        self._arguments = dict(global_kill_flag=global_kill_flag, worker_registry=worker_registry)
        self._manager = CameraGroupManager(**self._arguments)
        self.backend: CameraBackend = "python"

    async def create_or_update_camera_group(self, camera_configs, backend: CameraBackend = "python"):
        if backend != self.backend:
            if self._manager.camera_groups:
                raise CameraBackendInUseError("Close the current cameras before choosing another camera backend")
            from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
            implementation = CameraGroupManager if backend == "python" else RustCameraGroupManager
            self._manager = implementation(**self._arguments)
            self.backend = backend
        return await self._manager.create_or_update_camera_group(camera_configs)

    @property
    def camera_groups(self):
        return self._manager.camera_groups

    @property
    def closing(self):
        return self._manager.closing

    def get_camera_group(self, camera_group_id):
        return self._manager.get_camera_group(camera_group_id)

    async def close_all_camera_groups(self):
        await self._manager.close_all_camera_groups()

    async def start_recording_all_groups(self, recording_info):
        await self._manager.start_recording_all_groups(recording_info)

    async def stop_recording_all_groups(self):
        return await self._manager.stop_recording_all_groups()

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

    async def pause_unpause_all_groups(self, await_state_change=True):
        await self._manager.pause_unpause_all_groups(await_state_change)

    def find_camera_group_by_camera_ids(self, camera_ids):
        return self._manager.find_camera_group_by_camera_ids(camera_ids)

    def to_state_dict(self):
        state = self._manager.to_state_dict()
        for group in state["camera_groups"].values():
            group["backend"] = self.backend
        return state
