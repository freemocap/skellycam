import multiprocessing
from dataclasses import dataclass


@dataclass
class IPCFlags:
    global_kill_flag: multiprocessing.Value
    record_frames_flag: multiprocessing.Value
    mic_device_index: multiprocessing.Value
    kill_camera_group_flag: multiprocessing.Value
    cameras_connected_flag: multiprocessing.Value
    recording_nametag: multiprocessing.Array

    def __init__(self, global_kill_flag: multiprocessing.Value):
        self.global_kill_flag = global_kill_flag
        self.record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.cameras_connected_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.mic_device_index: multiprocessing.Value = multiprocessing.Value("i", -1)
        self.recording_nametag: multiprocessing.Array = multiprocessing.Array('c', 250)
        self.recording_nametag.value = b""

    @property
    def camera_group_should_continue(self):
        return not self.global_kill_flag.value and not self.kill_camera_group_flag.value

    @property
    def global_should_continue(self):
        return not self.global_kill_flag.value