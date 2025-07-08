import logging
from enum import Enum
from typing import List, Tuple
import time

import cv2
import numpy as np

MIN_EXPOSURE = -12  # Minimum exposure setting, in log base 2 seconds
MAX_EXPOSURE = -4  # Maximum exposure setting, in log base 2 seconds
NUMBER_OF_FRAMES_TO_SETTLE = 10  # Number of frames to allow camera to adjust to new exposure setting
TARGET_BRIGHTNESS = 127.5  # Target brightness value for optimal exposure setting, i.e. half of the maximum brightness of 255


class ExposureModes(float, Enum):
    # AUTO = 0.75  # Default value to activate auto exposure mode - windows
    AUTO = 3  # Default value to activate auto exposure mode - v4l
    # MANUAL = 0.25  # Default value to activate manual exposure mode - windows
    MANUAL = 1 # Default value to activate manual exposure mode - v4l
    RECOMMEND = -1 # Will find the optimal exposure setting which results in a brightness closest to 127.5 (i.e. half of the maximum brightness of 255)


# Set up logging
logger = logging.getLogger(__name__)


def capture_frame_with_exposure(cap: cv2.VideoCapture,
                                auto_manual_setting: ExposureModes,
                                exposure_setting: int | None = None,
                                ) -> float:
    """Capture a frame with the specified exposure setting and return its mean brightness."""
    time.sleep(2)
    _ = cap.read()  # Read a frame to ensure the camera is initialized
    if auto_manual_setting == ExposureModes.AUTO:
        ret_set = cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_manual_setting.value)
        print(f"Attempted to set auto exposure mode to {auto_manual_setting}: {ret_set}")
        if not ret_set:
            print(cap.get(cv2.CAP_PROP_AUTO_EXPOSURE))
    elif auto_manual_setting == ExposureModes.MANUAL:
        ret_set = cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_manual_setting.value)
        print(f"Attempted to set manual exposure mode to {auto_manual_setting}: {ret_set}")
        if not ret_set:
            print(cap.get(cv2.CAP_PROP_AUTO_EXPOSURE))
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure_setting)
    else:
        logger.exception(f"Invalid exposure mode: {auto_manual_setting}")
        raise ValueError(f"Invalid exposure mode: {auto_manual_setting}")

    # Allow time for camera to adjust
    for _ in range(NUMBER_OF_FRAMES_TO_SETTLE):
        success, _ = cap.read()
        if not success:
            logger.error("Failed to capture frame while adjusting exposure")
            raise Exception("Failed to capture frame while adjusting exposure")

    # Read a single frame
    success, image = cap.read()
    if success:
        brightness = np.mean(image)
        return float(brightness)
    else:
        logger.error("Failed to capture frame")
        raise Exception("Failed to capture frame")


def find_optimal_exposure_setting(cap: cv2.VideoCapture, exposure_settings: List[int]) -> int:
    """Find the exposure setting that results in a brightness closest to 127.5 (i.e. half of the maximum brightness of 255)."""
    logger.debug(
        "Starting search for optimal exposure setting, i.e. the setting that results in a brightness closest to 127.5 (half of the maximum brightness of 255)")

    # Store differences
    differences: List[Tuple[str, float, float]] = []

    # Capture frame in AUTO mode
    auto_brightness = capture_frame_with_exposure(cap, ExposureModes.AUTO)
    auto_difference = np.abs(TARGET_BRIGHTNESS - auto_brightness)
    differences.append(("9999", auto_brightness, auto_difference))

    for setting in exposure_settings:
        manual_brightness = capture_frame_with_exposure(cap=cap,
                                                        exposure_setting=setting,
                                                        auto_manual_setting=ExposureModes.MANUAL)
        difference = np.abs(TARGET_BRIGHTNESS - manual_brightness)
        differences.append((f"{setting}", manual_brightness, difference))

    # Find the setting with the smallest difference
    best_setting = min(differences, key=lambda x: x[2])

    # Annotate the differences with a marker for the best setting
    annotated_differences = [(row[0], row[1], f" {'>>   ' if row == best_setting else ''}{row[2]:.2f}") for row in
                             differences]

    # Print the results in a table format with right-justified difference column

    print("  Exposure Setting  |  Brightness | Difference from Target (127.5)")
    for row in annotated_differences:
        print(f"{row[0]:<20} {row[1]:>10.2f} {row[2]:>20}")
    return int(best_setting[0])

def get_recommended_cv2_cap_exposure(cap: cv2.VideoCapture | int, offset_from_midrange:int=-1) -> int | None:

    # List of exposure settings to test
    exposure_settings = list(range(MIN_EXPOSURE, MAX_EXPOSURE + 1))

    # Determine the optimal exposure setting
    try:
        if isinstance(cap, int):
            cap = cv2.VideoCapture(cap)
            if not cap.isOpened():
                logger.error(f"Failed to open camera with ID {cap}")
                raise ValueError(f"Failed to open camera with ID {cap}")
        midrange_exposure = find_optimal_exposure_setting(cap=cap,
                                                      exposure_settings=exposure_settings)
        recommended_exposure = midrange_exposure + offset_from_midrange
        logger.debug(f"The exposure setting that results in mid-range brightness is: {midrange_exposure}, recommended exposure setting is: {recommended_exposure}")
    except Exception as e:
        logger.exception("An error occurred during exposure optimization", exc_info=e)
        raise
    return recommended_exposure

if __name__ == "__main__":
    # Example usage
    camera_id = 0  # Replace with your camera ID
    cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        logger.error(f"Failed to open camera with ID {camera_id}")
    else:
        recommended_exposure = get_recommended_cv2_cap_exposure(cap=cap, offset_from_midrange=-1)
        if recommended_exposure is None:
            print("Failed to determine recommended exposure setting, setting to default 0.")
            recommended_exposure = 0
        print(f"Recommended exposure setting for camera {camera_id}: {recommended_exposure}")

        cap.set(cv2.CAP_PROP_EXPOSURE, recommended_exposure)

        ret, frame = cap.read()
        if ret:
            cv2.imshow(f"Camera {camera_id} - Recommended Exposure", frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        cap.release()
