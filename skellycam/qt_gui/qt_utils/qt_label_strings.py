import cv2

ROTATE_90_CLOCKWISE_STRING = "90 Clockwise"
ROTATE_90_COUNTERCLOCKWISE_STRING = "90 Counterclockwise"
ROTATE_180_STRING = "180"

COPY_SETTINGS_TO_CAMERAS_STRING = "Copy settings to all cameras"
USE_THIS_CAMERA_STRING = "Use this camera?"
EXPAND_ALL_STRING = "Expand All"
COLLAPSE_ALL_STRING = "Collapse All"


def rotate_image_str_to_cv2_code(rotate_str: str):
    if rotate_str == ROTATE_90_CLOCKWISE_STRING:
        return cv2.ROTATE_90_CLOCKWISE
    elif rotate_str == ROTATE_90_COUNTERCLOCKWISE_STRING:
        return cv2.ROTATE_90_COUNTERCLOCKWISE
    elif rotate_str == ROTATE_180_STRING:
        return cv2.ROTATE_180

    return None


def rotate_cv2_code_to_str(rotate_video_value):
    if rotate_video_value is None:
        return None
    elif rotate_video_value == cv2.ROTATE_90_CLOCKWISE:
        return ROTATE_90_CLOCKWISE_STRING
    elif rotate_video_value == cv2.ROTATE_90_COUNTERCLOCKWISE:
        return ROTATE_90_COUNTERCLOCKWISE_STRING
    elif rotate_video_value == cv2.ROTATE_180:
        return ROTATE_180_STRING
