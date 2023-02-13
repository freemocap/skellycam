from enum import Enum


class CameraGroupingStrategy(Enum):
    SAME_PROCESS = (0,)
    X_CAM_PER_PROCESS = 1

class CameraGroupManagmentStrategy(Enum):
    THREAD = (0,)
    PROCESS = 1
