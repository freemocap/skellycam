from enum import Enum

import cv2


class RotationTypes(Enum):
    NO_ROTATION = -1
    CLOCKWISE_90 = cv2.ROTATE_90_CLOCKWISE
    ROTATE_180 = cv2.ROTATE_180
    COUNTERCLOCKWISE_90 = cv2.ROTATE_90_COUNTERCLOCKWISE

def rotation_int_to_name(rotation_int: int) -> str:
    for rotation in RotationTypes:
        if rotation.value == rotation_int:
            return rotation.name
    return "UNKNOWN_ROTATION"
