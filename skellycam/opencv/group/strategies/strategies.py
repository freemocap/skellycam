from enum import Enum


class CameraManagementStrategy(Enum):
    SAME_PROCESS = (0,)
    X_CAM_PER_PROCESS = 1

class DataSharingStrategy(Enum):
    QUEUE = 0
    PIPE = 1
    SHARED_MEMORY = 2 #doesn't work, gets frozen somehow ( I think I dont handle the memory locking stuff properly)
    ZEROMQ = 3 #deprecated, could be easily updated to work
