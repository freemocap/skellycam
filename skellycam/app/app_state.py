import logging
import multiprocessing
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from skellycam.app.app_controller.ipc_flags import IPCFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import CameraGroupSharedMemoryOrchestrator
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.core.detection.camera_device_info import AvailableDevices, available_devices_to_default_camera_configs
from skellycam.core.frames.timestamps.frame_rate_tracker import CurrentFrameRate

logger = logging.getLogger(__name__)


class AppState:
    def __init__(self, global_kill_flag: multiprocessing.Value):

        self._global_kill_flag = global_kill_flag

        self._ipc_queue = multiprocessing.Queue()

        self._ipc_flags: Optional[IPCFlags] = IPCFlags(global_kill_flag=self._global_kill_flag)

        self._shmorchestrator: Optional[CameraGroupSharedMemoryOrchestrator] = None
        self._camera_group: Optional[CameraGroup] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._current_frame_rate: Optional[CurrentFrameRate] = None

    @property
    def ipc_flags(self) -> IPCFlags:
        return self._ipc_flags

    @property
    def ipc_queue(self) -> multiprocessing.Queue:
        return self._ipc_queue

    @property
    def camera_group(self) -> CameraGroup:
        return self._camera_group

    @property
    def current_frame_rate(self) -> CurrentFrameRate:
        return self._current_frame_rate

    @property
    def orchestrator(self) -> CameraGroupOrchestrator:
        return self._shmorchestrator.camera_group_orchestrator

    @property
    def camera_group_shm(self) -> CameraGroupSharedMemory:
        return self._shmorchestrator.camera_group_shm

    @property
    def shmorchestrator(self) -> Optional[CameraGroupSharedMemoryOrchestrator]:
        return self._shmorchestrator

    @property
    def camera_group_configs(self) -> Optional[CameraConfigs]:
        if self._camera_group is None:
            if self._available_devices is None:
                return None
            return available_devices_to_default_camera_configs(self._available_devices)
        return self._camera_group.camera_configs

    @property
    def available_devices(self) -> Optional[AvailableDevices]:
        return self._available_devices

    @available_devices.setter
    def available_devices(self, value):
        self._available_devices = value

        self._ipc_queue.put(self.state_dto())

    def create_camera_group(self, camera_configs: CameraConfigs):
        # NOTE top-level shmorchestrator is read-only
        self._shmorchestrator = CameraGroupSharedMemoryOrchestrator.create(camera_configs=camera_configs,
                                                                           ipc_flags=self._ipc_flags,
                                                                           read_only=True)
        self._camera_group = CameraGroup.create(dto=CameraGroupDTO(shmorc_dto=self._shmorchestrator.to_dto(),
                                                                   camera_configs=camera_configs,
                                                                   ipc_queue=self._ipc_queue,
                                                                   ipc_flags=self._ipc_flags)
                                                )

    async def update_camera_group(self,
                                  camera_configs: CameraConfigs,
                                  update_instructions: UpdateInstructions):
        if self._camera_group is None:
            raise ValueError("Cannot update CameraGroup if it does not exist!")
        await self._camera_group.update_camera_configs(camera_configs=camera_configs,
                                                       update_instructions=update_instructions)

    async def close_camera_group(self):
        logger.debug("Closing existing camera group...")
        self._ipc_flags.kill_camera_group_flag.value = True
        await self._camera_group.close()
        self._camera_group = None
        self._shmorchestrator = None
        self._ipc_flags = IPCFlags(global_kill_flag=self._global_kill_flag)
        self._current_frame_rate = None
        logger.success("Camera group closed successfully")

    def start_recording(self):
        self._ipc_flags.record_frames_flag.value = True
        self._ipc_queue.put(self.state_dto())

    def stop_recording(self):
        self._ipc_flags.record_frames_flag.value = False
        self._ipc_queue.put(self.state_dto())

    def state_dto(self) -> 'AppStateDTO':
        return AppStateDTO.from_state(self)


class AppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the AppState
    """
    state_timestamp: str = datetime.now().isoformat()

    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableDevices]
    current_frame_rate: Optional[CurrentFrameRate]
    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: AppState):
        return cls(
            camera_configs=state.camera_group_configs,
            available_devices=state.available_devices,
            current_frame_rate=state.current_frame_rate,
            record_frames_flag_status=state.ipc_flags.record_frames_flag.value,
        )


APP_STATE = None


def create_app_state(global_kill_flag: multiprocessing.Event) -> AppState:
    global APP_STATE
    if APP_STATE is None:
        APP_STATE = AppState(global_kill_flag=global_kill_flag)
    return APP_STATE


def get_app_state():
    global APP_STATE
    if APP_STATE is None:
        raise ValueError("AppState not created!")
    return APP_STATE
