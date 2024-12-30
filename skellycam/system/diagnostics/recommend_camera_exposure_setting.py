import logging
from enum import Enum
from typing import List, Tuple

import cv2
import numpy as np
from tabulate import tabulate

MIN_EXPOSURE = -12  # Minimum exposure setting, in log base 2 seconds
MAX_EXPOSURE = -4  # Maximum exposure setting, in log base 2 seconds
NUMBER_OF_FRAMES_TO_SETTLE = 10  # Number of frames to allow camera to adjust to new exposure setting
TARGET_BRIGHTNESS = 127.5  # Target brightness value for optimal exposure setting, i.e. half of the maximum brightness of 255


class ExposureModes(float, Enum):
    AUTO = 0.75  # Default value to activate auto exposure mode
    MANUAL = 0.25  # Default value to activate manual exposure mode
    RECOMMENDED = -1 # Will find the optimal exposure setting which results in a brightness closest to 127.5 (i.e. half of the maximum brightness of 255)


# Set up logging
logger = logging.getLogger(__name__)


def capture_frame_with_exposure(cap: cv2.VideoCapture,
                                auto_manual_setting: ExposureModes,
                                exposure_setting: int | None = None,
                                ) -> float:
    """Capture a frame with the specified exposure setting and return its mean brightness."""
    if auto_manual_setting == ExposureModes.AUTO:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_manual_setting.value)
    elif auto_manual_setting == ExposureModes.MANUAL:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_manual_setting.value)
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
        return brightness
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
    # auto_brightness = capture_frame_with_exposure(cap, ExposureModes.AUTO)
    # auto_difference = np.abs(TARGET_BRIGHTNESS - auto_brightness)
    # differences.append(("AUTO", auto_brightness, auto_difference))

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
    headers = ["Exposure Setting", "Brightness", "Difference from Target (127.5)"]
    table = tabulate(annotated_differences, headers=headers, floatfmt=".2f", colalign=("left", "center", "right"))
    logger.debug("\n" + table)




    return int(best_setting[0])

def get_recommended_cv2_cap_exposure(cap: cv2.VideoCapture | int, offset_from_midrange:int=-1) -> int | None:
    release_cap = False
    if isinstance(cap, int):
        cap = cv2.VideoCapture(cap)
        release_cap = True

    # List of exposure settings to test
    exposure_settings = list(range(MIN_EXPOSURE, MAX_EXPOSURE + 1))

    # Determine the optimal exposure setting
    try:
        midrange_exposure = find_optimal_exposure_setting(cap=cap,
                                                      exposure_settings=exposure_settings)
        recommended_exposure = midrange_exposure + offset_from_midrange
        logger.debug(f"The exposure setting that results in mid-range brightness is: {midrange_exposure}, recommended exposure setting is: {recommended_exposure}")
    except Exception as e:
        logger.exception("An error occurred during exposure optimization")
        if release_cap:
            cap.release()
        return None
    finally:
        if release_cap:
            cap.release()
    return recommended_exposure


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Starting exposure optimization...")
    get_recommended_cv2_cap_exposure(0)
