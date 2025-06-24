from enum import Enum

import cv2

OPENCV_NO_ROTATION_PLACEHOLDER_VALUE= 99 # using 99 instead of -1 because this will need to be a `uint` later

class RotationTypes(str, Enum):
    NO_ROTATION = "0"
    CLOCKWISE_90 = "90"
    ROTATE_180 = "180"
    COUNTERCLOCKWISE_90 = "270"

    def to_opencv_constant(self) -> int:
        rotation_mapping = {
            RotationTypes.NO_ROTATION: OPENCV_NO_ROTATION_PLACEHOLDER_VALUE, # N/A
            RotationTypes.CLOCKWISE_90: cv2.ROTATE_90_CLOCKWISE, # 0
            RotationTypes.ROTATE_180: cv2.ROTATE_180, # 1
            RotationTypes.COUNTERCLOCKWISE_90: cv2.ROTATE_90_COUNTERCLOCKWISE,  # 2

        }
        return rotation_mapping[self]
