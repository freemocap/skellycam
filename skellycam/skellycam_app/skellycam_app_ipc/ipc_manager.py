import multiprocessing
from dataclasses import dataclass

from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue


@dataclass
class InterProcessCommunicationManager:
    global_kill_flag: multiprocessing.Value
    record_frames_flag: multiprocessing.Value
    kill_camera_group_flag: multiprocessing.Value
    cameras_connected_flag: multiprocessing.Value
    recording_name: multiprocessing.Array


    ws_ipc_relay_queue: multiprocessing.Queue
    ws_logs_queue: multiprocessing.Queue
    update_camera_configs_queue: multiprocessing.Queue
    recording_control_queue: multiprocessing.Queue


    def __init__(self, global_kill_flag: multiprocessing.Value):
        self.global_kill_flag = global_kill_flag
        self.kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.cameras_connected_flag: multiprocessing.Value = multiprocessing.Value("b", False)

        self.record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.start_recording_queue: multiprocessing.Queue = multiprocessing.Queue()

        self.ws_ipc_relay_queue: multiprocessing.Queue  = multiprocessing.Queue()
        self.ws_logs_queue: multiprocessing.Queue  = get_websocket_log_queue()
        self.update_camera_configs_queue: multiprocessing.Queue  = multiprocessing.Queue()
        self.recording_control_queue: multiprocessing.Queue  = multiprocessing.Queue()

    @property
    def camera_group_should_continue(self):
        return not self.global_kill_flag.value and not self.kill_camera_group_flag.value

    @property
    def global_should_continue(self):
        return not self.global_kill_flag.value