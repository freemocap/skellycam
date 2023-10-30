from enum import Enum

import cv2


class RotationTypes(Enum):
    NO_ROTATION = None
    CLOCKWISE_90 = cv2.ROTATE_90_CLOCKWISE
    COUNTERCLOCKWISE_90 = cv2.ROTATE_90_COUNTERCLOCKWISE
    ROTATE_180 = cv2.ROTATE_180

    def __str__(self):
        match self:
            case RotationTypes.NO_ROTATION:
                return "No rotation"
            case RotationTypes.CLOCKWISE_90:
                return "Clockwise 90 degrees"
            case RotationTypes.COUNTERCLOCKWISE_90:
                return "Counterclockwise 90 degrees"
            case RotationTypes.ROTATE_180:
                return "Rotate 180 degrees"

        raise ValueError(f"Unknown rotation type: {self}")

    @classmethod
    def as_strings(cls):
        return [str(member.name) for member in cls]
