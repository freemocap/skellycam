import logging
import multiprocessing
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.detection.camera_device_info import AvailableDevices


class WebSocketStatus(BaseModel):
    connected: bool = False
    ping_interval_ns: Optional[int] = None


class ProcessStatus(BaseModel):
    process_name: str
    is_alive: bool
    pid: str
    parent_pid: str

    @classmethod
    def from_process(cls, process: multiprocessing.Process,
                     parent_pid: int):
        return cls(
            process_name=process.name,
            is_alive=process.is_alive(),
            pid=str(process.pid),
            parent_pid=str(parent_pid),
        )


class ApiCallLog(BaseModel):
    url_path: str
    log_timestamp: str = datetime.now().isoformat()
    start_time: float
    process_time: float
    status_code: int

    @classmethod
    def create(cls, url_path: str, timestamp: float, process_time: float, status_code: int):
        return cls(
            url_path=url_path,
            start_time=timestamp,
            process_time=process_time,
            status_code=status_code,
        )


logger = logging.getLogger(__name__)


class AppState:
    def __init__(self):
        self._camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._websocket_status: Optional[WebSocketStatus] = None
        self._api_call_history: List[ApiCallLog] = []
        self._processes: Optional[Dict[str, ProcessStatus]] = None

        self._record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self._kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)

        self._lock = multiprocessing.Lock()

    @property
    def camera_configs(self):
        with self._lock:
            return self._camera_configs

    @camera_configs.setter
    def camera_configs(self, value):
        with self._lock:
            self._camera_configs = value

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

    @property
    def websocket_status(self):
        with self._lock:
            return self._websocket_status

    @websocket_status.setter
    def websocket_status(self, value):
        with self._lock:
            self._websocket_status = value

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

    @property
    def kill_camera_group_flag(self):
        if self._kill_camera_group_flag is None:
            return False
        with self._lock:
            return self._kill_camera_group_flag

    @kill_camera_group_flag.setter
    def kill_camera_group_flag(self, value: multiprocessing.Value):
        with self._lock:
            self._kill_camera_group_flag = value

    @property
    def api_call_history(self):
        with self._lock:
            return self._api_call_history

    @property
    def processes(self):
        with self._lock:
            return self._processes

    def log_api_call(self, url_path: str, start_time: float, process_time: float, status_code: int):
        with self._lock:
            self._api_call_history.append(ApiCallLog.create(url_path=url_path,
                                                            timestamp=start_time,
                                                            process_time=process_time,
                                                            status_code=status_code))

    def add_process(self, process: multiprocessing.Process, parent_pid: int):
        with self._lock:
            self._processes[str(process.pid)] = ProcessStatus.from_process(process=process, parent_pid=parent_pid)

    def remove_processes(self, process: multiprocessing.Process):
        with self._lock:
            self._processes.pop(str(process.pid))

    def update(self, new_data: Any):
        with self._lock:
            if isinstance(new_data, CameraConfigs):
                self.camera_configs = new_data
            elif isinstance(new_data, AvailableDevices):
                self.available_devices = new_data
            elif isinstance(new_data, WebSocketStatus):
                self.websocket_status = new_data
            elif isinstance(new_data, ProcessStatus):
                self._processes[new_data.pid] = new_data
            else:
                logger.exception(f"Unknown data type: {new_data}")
                raise ValueError(f"Unknown data type: {new_data}")

    def state(self) -> 'AppStateDTO':
        return AppStateDTO.from_state(self)


class AppStateDTO(BaseModel):
    """
    Data Transfer Object for the AppState
    """
    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableDevices]
    websocket_status: Optional[WebSocketStatus]

    api_call_history: Optional[List[ApiCallLog]]
    processes: Optional[Dict[str, ProcessStatus]]

    record_frames_flag: bool
    kill_camera_group_flag: bool

    @classmethod
    def from_state(cls, state: AppState):
        return cls(
            camera_configs=state.camera_configs,
            available_devices=state.available_devices,
            websocket_status=state.websocket_status,
            record_frames_flag=state.record_frames_flag,
            kill_camera_group_flag=state.kill_camera_group_flag,
            api_call_history=state.api_call_history,
            processes=state.processes,
        )


APP_STATE = None


def get_app_state():
    global APP_STATE
    if APP_STATE is None:
        APP_STATE = AppState()
    return APP_STATE
