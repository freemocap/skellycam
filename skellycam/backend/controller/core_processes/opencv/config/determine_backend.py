import logging
import platform

import cv2

from skellycam import logger


def determine_backend():
    if platform.system() == "Windows":
        logger.debug(f"Windows machine detected - using backend `cv2.CAP_DSHOW`")
        return cv2.CAP_DSHOW
    else:
        logger.debug(f"Non-Windows machine detected - using backend `cv2.CAP_ANY`")
        return cv2.CAP_ANY
