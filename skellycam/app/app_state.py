import logging
import multiprocessing
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.camera_group.camera_group import CameraGroup, CameraGroupDTO
from skellycam.core.camera_group.camera_group_shmorchestrator import CameraGroupSharedMemoryOrchestrator

logger = logging.getLogger(__name__)


class IPCFlags(BaseModel):
    global_kill_flag: multiprocessing.Value
    record_frames_flag = multiprocessing.Value("b", False)
    kill_camera_group_flag = multiprocessing.Value("b", False)


class AppState:
    def __init__(self, global_kill_flag: multiprocessing.Value):

        self._global_kill_flag = global_kill_flag

        self._ipc_publish_queue = multiprocessing.Queue()

        self._ipc_flags: Optional[IPCFlags] = None
        self._shmorchestrator: Optional[CameraGroupSharedMemoryOrchestrator] = None
        self._camera_group: Optional[CameraGroup] = None
        self._available_devices: Optional[AvailableDevices] = None

        self._lock = multiprocessing.Lock()

    @property
    def ipc_flags(self) -> IPCFlags:
        return self._ipc_flags

    @property
    def camera_group(self) -> CameraGroup:
        return self._camera_group

    def create_camera_group(self, camera_configs: CameraConfigs):
        self._shmorchestrator = CameraGroupSharedMemoryOrchestrator.create(camera_configs=camera_configs,
                                                                           ipc_flags=self._ipc_flags,
                                                                           read_only=True
                                                                           # NOTE top-level shmorchestrator is read-only
                                                                           )
        self._camera_group = CameraGroup.create(dto=CameraGroupDTO(
            shmorc_dto=self._shmorchestrator.to_dto(),
            camera_configs=camera_configs,
            ipc_publish_queue=self._ipc_publish_queue,
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
        self._ipc_flags = None
        logger.success("Camera group closed successfully")

    @property
    def shmorchestrator(self) -> CameraGroupSharedMemoryOrchestrator:
        if self._shmorchestrator is None:
            raise ValueError("CameraGroupSharedMemoryOrchestrator not created!")
        return self._shmorchestrator

    def camera_group_configs(self, value):
        with self._lock:
            if value is None:
                self._camera_group_configs = None
            else:
                if self._available_devices is None:
                    raise ValueError("Cannot set `camera_configs` if `available_cameras` is None! ")
                if any([camera_id not in self._available_devices.keys() for camera_id in value.keys()]):
                    raise ValueError(
                        f"Not all camera config id's [{value.keys()}] present in `available_camera` id's [{self._available_devices.keys()}]")
                self._camera_group_configs = value
        self._ipc_publish_queue.put(self.state_dto())

    @property
    def available_devices(self):
        with self._lock:
            return self._available_devices

    @available_devices.setter
    def available_devices(self, value):
        with self._lock:
            self._available_devices = value

            if self._camera_group_configs is None:
                self._camera_group_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in
                                              self._available_devices.keys()}
        self._ipc_publish_queue.put(self.state_dto())

    def start_recording(self):
        with self._lock:
            self._ipc_flags.record_frames_flag.value = True
        self._ipc_publish_queue.put(self.state_dto())

    def stop_recording(self):
        with self._lock:
            self._ipc_flags.record_frames_flag.value = False
        self._ipc_publish_queue.put(self.state_dto())

    def state_dto(self) -> 'AppStateDTO':
        return AppStateDTO.from_state(self)


class AppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the AppState
    """
    state_timestamp: str = datetime.now().isoformat()

    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableDevices]

    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: AppState):
        return cls(
            camera_configs=state.camera_group_configs,
            available_devices=state.available_devices,
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
