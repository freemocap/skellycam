import multiprocessing


class IPCFlags:
    global_kill_flag: multiprocessing.Value
    record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
    kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)

    def __init__(self, global_kill_flag: multiprocessing.Value):
        self.global_kill_flag = global_kill_flag
