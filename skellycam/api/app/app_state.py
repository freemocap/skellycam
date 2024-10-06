import logging
import multiprocessing
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from skellycam.api.websocket.ipc import get_ipc_queue
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO, CameraGroupSharedMemory


class WebSocketStatus(BaseModel):
    connected: bool = False
    ping_interval_ns: Optional[int] = None





logger = logging.getLogger(__name__)


class AppState:
    def __init__(self):
        self._camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._websocket_status: Optional[WebSocketStatus] = None

        self._record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self._kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)

        self._lock = multiprocessing.Lock()

        self._ipc_queue = get_ipc_queue()

        self._camera_group_shm: Optional[CameraGroupSharedMemory]= None
        self._camera_group_shm_valid_flag: multiprocessing.Value = multiprocessing.Value("b", False)


    @property
    def camera_configs(self) -> CameraConfigs:
        with self._lock:
            return self._camera_configs

    @camera_configs.setter
    def camera_configs(self, value):
        with self._lock:
            if self._available_devices is None:
                raise ValueError("Cannot set `camera_configs` if `available_cameras` is None! ")
            if any([camera_id not in self._available_devices.keys() for camera_id in value.keys()]):
                raise ValueError(
                    f"Not all camera config id's [{value.keys()}] present in `available_camera` id's [{self._available_devices.keys()}]")
            self._camera_configs = value
        self._ipc_queue.put(self.state_dto())

    @property
    def available_devices(self):
        with self._lock:
            return self._available_devices

    @available_devices.setter
    def available_devices(self, value):
        with self._lock:
            self._available_devices = value

            if self._camera_configs is None:
                self._camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in
                                        self._available_devices.keys()}
        self._ipc_queue.put(self.state_dto())

    @property
    def websocket_status(self):
        with self._lock:
            return self._websocket_status

    @websocket_status.setter
    def websocket_status(self, value):
        with self._lock:
            self._websocket_status = value
        self._ipc_queue.put(self.state_dto())

    @property
    def record_frames_flag(self):
        if self._record_frames_flag is None:
            return False
        with self._lock:
            return self._record_frames_flag

    @record_frames_flag.setter
    def record_frames_flag(self, value: multiprocessing.Value):
        with self._lock:
            self._record_frames_flag = value
        self._ipc_queue.put(self.state_dto())

    @property
    def shm_valid_flag(self):
        with self._lock:
            return self._camera_group_shm_valid_flag

    def state_dto(self) -> 'AppStateDTO':
        return AppStateDTO.from_state(self)

    def create_camera_group_shm(self):
        if self._camera_configs is None:
            raise ValueError("Cannot create camera group shared memory without camera configs!")

        if self._camera_group_shm is not None:
            self.close_camera_group_shm()

        self._camera_group_shm = CameraGroupSharedMemory.create(camera_configs=self._camera_configs)
        self._camera_group_shm_valid_flag.value = True

    def get_camera_group_shm_dto(self) -> CameraGroupSharedMemoryDTO:
        if self._camera_group_shm is None:
            raise ValueError("Cannot get camera group shared memory DTO without camera group shared memory!")
        with self._lock:
            return self._camera_group_shm.to_dto()

    def close_camera_group_shm(self):
        if self._camera_group_shm is not None:
            self._camera_group_shm_valid_flag.value = False
            self._camera_group_shm.close_and_unlink()
            self._camera_group_shm = None

class AppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the AppState
    """
    state_timestamp: str = datetime.now().isoformat()


    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableDevices]
    websocket_status: Optional[WebSocketStatus]

    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: AppState):
        return cls(
            camera_configs=state.camera_configs,
            available_devices=state.available_devices,
            websocket_status=state.websocket_status,
            record_frames_flag_status=state.record_frames_flag.value,
        )


APP_STATE = None


def get_app_state():
    global APP_STATE
    if APP_STATE is None:
        APP_STATE = AppState()
    return APP_STATE
