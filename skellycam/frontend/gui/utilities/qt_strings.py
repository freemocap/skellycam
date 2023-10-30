import cv2

import skellycam
from skellycam.models.cameras.image_rotation_types import ROTATE_90_CLOCKWISE_STRING, ROTATE_90_COUNTERCLOCKWISE_STRING, \
    ROTATE_180_STRING
from skellycam.system.environment.default_paths import MAGNIFYING_GLASS_EMOJI_STRING, CAMERA_WITH_FLASH_EMOJI_STRING, \
    CLOCKWISE_VERTICAL_ARROWS_EMOJI_STRING, RED_X_EMOJI_STRING, HAMMER_AND_WRENCH_EMOJI_STRING



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
DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT = f"Detect Available Cameras {MAGNIFYING_GLASS_EMOJI_STRING}"
CONNECT_TO_CAMERAS_BUTTON_TEXT = f"Connect to Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}"
RESET_CAMERA_SETTINGS_BUTTON_TEXT = f"Reset Camera Settings {CLOCKWISE_VERTICAL_ARROWS_EMOJI_STRING}"
APPLY_CAMERA_SETTINGS_BUTTON_TEXT = f"Apply camera settings {HAMMER_AND_WRENCH_EMOJI_STRING}"
CLOSE_CAMERAS_BUTTON_TEXT = f"Close Cameras {RED_X_EMOJI_STRING}"
STOP_RECORDING_BUTTON_TEXT = "\U00002B1B Stop Recording"
START_RECORDING_BUTTON_TEXT = "\U0001F534 Start Recording"
