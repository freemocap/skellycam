import cv2

import skellycam

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


no_cameras_found_message_string = "\n\n"
no_cameras_found_message_string += "No cameras found! \n \n"
no_cameras_found_message_string += "Please check your camera connections and try again. \n"
no_cameras_found_message_string += "\n"
no_cameras_found_message_string += "  - If you are using a USB hub, try connecting your cameras directly to a USB port on your computer (move your mouse/keyboard/etc peripherals to the USB hub to free up ports). \n"
no_cameras_found_message_string += "  - If that doesn't work, try (in order of increasing escalation): \n"
no_cameras_found_message_string += "    - Unplug and re-plug your cameras \n"
no_cameras_found_message_string += f"    - Restart your the `{skellycam.__package_name__}` application \n"
no_cameras_found_message_string += "    - Restart your computer \n"
no_cameras_found_message_string += f"    - Submit an Issue on the Github: {skellycam.__repo_issues_url__}  (include a copy of the `log` file from this session)\n"
