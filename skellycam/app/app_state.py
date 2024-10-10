import logging
import multiprocessing
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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


class AppState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ipc_flags: IPCFlags
    ipc_queue: multiprocessing.Queue = Field(default_factory=lambda: multiprocessing.Queue())

    shmorchestrator: Optional[CameraGroupSharedMemoryOrchestrator] = None
    camera_group: Optional[CameraGroup] = None
    available_devices: Optional[AvailableDevices] = None
    current_frame_rate: Optional[CurrentFrameRate] = None

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls(ipc_flags=IPCFlags(global_kill_flag=global_kill_flag))


    @property
    def orchestrator(self) -> CameraGroupOrchestrator:
        return self.shmorchestrator.camera_group_orchestrator

    @property
    def camera_group_shm(self) -> CameraGroupSharedMemory:
        return self.shmorchestrator.camera_group_shm


    @property
    def camera_group_configs(self) -> Optional[CameraConfigs]:
        if self.camera_group is None:
            if self.available_devices is None:
                return None
            return available_devices_to_default_camera_configs(self.available_devices)
        return self.camera_group.camera_configs


    def set_available_devices(self, value:AvailableDevices):
        self.available_devices = value
        self.ipc_queue.put(self.state_dto())

    def create_camera_group(self):
        self.shmorchestrator = CameraGroupSharedMemoryOrchestrator.create(camera_configs=self.camera_group_configs,
                                                                           ipc_flags=self.ipc_flags,
                                                                           read_only=True)
        self.camera_group = CameraGroup.create(dto=CameraGroupDTO(shmorc_dto=self.shmorchestrator.to_dto(),
                                                                   camera_configs=self.camera_group_configs,
                                                                   ipc_queue=self.ipc_queue,
                                                                   ipc_flags=self.ipc_flags)
                                                )
        logger.info(f"Camera group created successfully for cameras: {self.camera_group.camera_ids}")

    async def update_camera_group(self,
                                  camera_configs: CameraConfigs,
                                  update_instructions: UpdateInstructions):
        if self.camera_group is None:
            raise ValueError("Cannot update CameraGroup if it does not exist!")
        await self.camera_group.update_camera_configs(camera_configs=camera_configs,
                                                       update_instructions=update_instructions)

    async def close_camera_group(self):
        if self.camera_group is None:
            logger.warning("Camera group does not exist, so it cannot be closed!")
            return
        logger.debug("Closing existing camera group...")
        self.ipc_flags.kill_camera_group_flag.value = True
        await self.camera_group.close()
        self.reset()
        logger.success("Camera group closed successfully")

    def start_recording(self):
        self.ipc_flags.record_frames_flag.value = True
        self.ipc_queue.put(self.state_dto())

    def stop_recording(self):
        self.ipc_flags.record_frames_flag.value = False
        self.ipc_queue.put(self.state_dto())

    def state_dto(self) -> 'AppStateDTO':
        return AppStateDTO.from_state(self)

    def _reset(self):
        self.camera_group = None
        self.shmorchestrator = None
        self.available_devices = None
        self.current_frame_rate = None
        self.ipc_flags = IPCFlags(global_kill_flag=self.global_kill_flag)


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
        APP_STATE = AppState.create(global_kill_flag=global_kill_flag)
    return APP_STATE


def get_app_state():
    global APP_STATE
    if APP_STATE is None:
        raise ValueError("AppState not created!")
    return APP_STATE
