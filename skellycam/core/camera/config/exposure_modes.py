from enum import Enum


class ExposureModes(float, Enum):
    AUTO = 0.75
    MANUAL = 0.25
    RECOMMEND = -1
