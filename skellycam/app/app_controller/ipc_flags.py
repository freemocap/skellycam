import multiprocessing
from dataclasses import dataclass


@dataclass
class IPCFlags:
    global_kill_flag: multiprocessing.Value
    record_frames_flag: multiprocessing.Value
    kill_camera_group_flag: multiprocessing.Value

    def __init__(self, global_kill_flag: multiprocessing.Value):
        self.global_kill_flag = global_kill_flag
        self.record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)

    def __post_init__(self):
        if not isinstance(self.global_kill_flag, multiprocessing.Value):
            raise ValueError(f"Expected multiprocessing.Value for global_kill_flag, got {type(self.global_kill_flag)}")
        if not isinstance(self.record_frames_flag, multiprocessing.Value):
            raise ValueError(f"Expected multiprocessing.Value for record_frames_flag, got {type(self.record_frames_flag)}")
        if not isinstance(self.kill_camera_group_flag, multiprocessing.Value):
            raise ValueError(f"Expected multiprocessing.Value for kill_camera_group_flag, got {type(self.kill_camera_group_flag)}")
