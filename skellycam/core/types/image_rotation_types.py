from enum import Enum

import cv2


class RotationTypes(Enum):
    NO_ROTATION = -1
    CLOCKWISE_90 = cv2.ROTATE_90_CLOCKWISE
    ROTATE_180 = cv2.ROTATE_180
    COUNTERCLOCKWISE_90 = cv2.ROTATE_90_COUNTERCLOCKWISE

