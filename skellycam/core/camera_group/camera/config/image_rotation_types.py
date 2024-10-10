from enum import Enum

import cv2


class RotationTypes(str, Enum):
    NO_ROTATION = "No Rotation"
    CLOCKWISE_90 = "90 Clockwise"
    COUNTERCLOCKWISE_90 = "90 Counterclockwise"
    ROTATE_180 = "180"

    def to_opencv_constant(self) -> int:
        rotation_mapping = {
            RotationTypes.NO_ROTATION: None,
            RotationTypes.CLOCKWISE_90: cv2.ROTATE_90_CLOCKWISE,
            RotationTypes.COUNTERCLOCKWISE_90: cv2.ROTATE_90_COUNTERCLOCKWISE,
            RotationTypes.ROTATE_180: cv2.ROTATE_180,
        }
        return rotation_mapping[self]

