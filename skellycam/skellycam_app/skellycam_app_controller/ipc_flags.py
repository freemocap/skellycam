import multiprocessing
from dataclasses import dataclass
import ctypes


@dataclass
class IPCFlags:
    global_kill_flag: multiprocessing.Value
    record_frames_flag: multiprocessing.Value
    mic_device_index: multiprocessing.Value
    kill_camera_group_flag: multiprocessing.Value
    cameras_connected_flag: multiprocessing.Value
    recording_nametag: multiprocessing.Value

    def __init__(self, global_kill_flag: multiprocessing.Value):
        self.global_kill_flag = global_kill_flag
        self.record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.cameras_connected_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.mic_device_index: multiprocessing.Value = multiprocessing.Value("i", -1)
        self.recording_nametag: multiprocessing.Value = multiprocessing.Value(ctypes.c_wchar_p, "")

