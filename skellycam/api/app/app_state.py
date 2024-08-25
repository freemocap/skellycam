import logging
import multiprocessing
from datetime import datetime
from typing import Optional, List, Dict

import psutil
from pydantic import BaseModel

from skellycam.api.routes.websocket.ipc import get_ipc_queue
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.detection.camera_device_info import AvailableDevices


class WebSocketStatus(BaseModel):
    connected: bool = False
    ping_interval_ns: Optional[int] = None


class SubProcessStatus(BaseModel):
    process_name: str
    is_alive: bool
    pid: int
    parent_pid: str

    @classmethod
    def from_process(cls, process: multiprocessing.Process,
                     parent_pid: int):
        return cls(
            process_name=process.name,
            is_alive=process.is_alive(),
            pid=process.pid,
            parent_pid=str(parent_pid),
        )


class TaskStatus(BaseModel):
    task_name: str
    is_running: bool

    @classmethod
    def from_task(cls, task: multiprocessing.Process):
        return cls(
            task_name=task.name,
            is_running=task.is_alive(),
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

        self._subprocess_statuses: Optional[Dict[int, SubProcessStatus]] = None
        self._task_statuses: Optional[Dict[str, TaskStatus]] = None

        self._record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self._kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)

        self._lock = multiprocessing.Lock()

        self._ipc_queue = get_ipc_queue()

    @property
    def camera_configs(self):
        with self._lock:
            return self._camera_configs

    @camera_configs.setter
    def camera_configs(self, value):
        with self._lock:
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
    def kill_camera_group_flag(self):
        if self._kill_camera_group_flag is None:
            return False
        with self._lock:
            return self._kill_camera_group_flag

    @kill_camera_group_flag.setter
    def kill_camera_group_flag(self, value: multiprocessing.Value):
        with self._lock:
            self._kill_camera_group_flag = value
        self._ipc_queue.put(self.state_dto())

    @property
    def api_call_history(self):
        with self._lock:
            return self._api_call_history

    @property
    def subprocess_statuses(self) -> Dict[int, SubProcessStatus]:
        with self._lock:
            for process_status in self._subprocess_statuses.values() if self._subprocess_statuses else []:
                if not psutil.Process(process_status.pid).is_running():
                    self._subprocess_statuses.pop(process_status.pid)

            return self._subprocess_statuses

    def log_api_call(self, url_path: str, start_time: float, process_time: float, status_code: int):
        with self._lock:
            self._api_call_history.append(ApiCallLog.create(url_path=url_path,
                                                            timestamp=start_time,
                                                            process_time=process_time,
                                                            status_code=status_code))
        self._ipc_queue.put(self.state_dto())

    def update_process_status(self, process_status: SubProcessStatus):
        with self._lock:
            if self._subprocess_statuses is None:
                self._subprocess_statuses = {}
            if process_status.is_alive:
                self._subprocess_statuses[process_status.pid] = process_status
            else:
                self._subprocess_statuses.pop(process_status.pid, None)
        self._ipc_queue.put(self.state_dto())

    @property
    def task_statuses(self):
        with self._lock:
            return self._task_statuses

    def update_task_status(self, task_status: Optional[TaskStatus]):
        if not task_status:
            return
        with self._lock:
            if self._task_statuses is None:
                self._task_statuses = {}
            if task_status.is_running:
                self._task_statuses[task_status.task_name] = task_status
            else:
                self._task_statuses.pop(task_status.task_name, None)
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
    websocket_status: Optional[WebSocketStatus]

    api_call_history: Optional[List[ApiCallLog]]
    subprocess_statuses: Optional[Dict[int, SubProcessStatus]]
    task_statuses: Optional[Dict[str, TaskStatus]]

    record_frames_flag_status: bool
    kill_camera_group_flag_status: bool

    @classmethod
    def from_state(cls, state: AppState):
        return cls(
            camera_configs=state.camera_configs,
            available_devices=state.available_devices,
            websocket_status=state.websocket_status,
            record_frames_flag_status=state.record_frames_flag.value,
            kill_camera_group_flag_status=state.kill_camera_group_flag.value,
            api_call_history=state.api_call_history,
            subprocess_statuses=state.subprocess_statuses,
            task_statuses=state.task_statuses,
        )


APP_STATE = None


def get_app_state():
    global APP_STATE
    if APP_STATE is None:
        APP_STATE = AppState()
    return APP_STATE
