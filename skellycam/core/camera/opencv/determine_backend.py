import enum
import platform

import cv2


class BackendSelection(enum.Enum):
    CAP_ANY = cv2.CAP_ANY
    CAP_FFMPEG = cv2.CAP_FFMPEG
    CAP_OPENCV_MJPEG = cv2.CAP_OPENCV_MJPEG
    CAP_DSHOW = cv2.CAP_DSHOW
    CAP_MSMF = cv2.CAP_MSMF
    CAP_VFW = cv2.CAP_VFW
    CAP_V4L = cv2.CAP_V4L
    CAP_V4L2 = cv2.CAP_V4L2
    CAP_QT = cv2.CAP_QT


def determine_backend() -> BackendSelection:
    if platform.system() == "Windows":
        return BackendSelection.CAP_DSHOW
    else:
        return BackendSelection.CAP_ANY  # TODO - Figure out how to do this better for non-Windows systems, this works on Linux but seems to max at 25fps (for 30fps camera)


if __name__ == "__main__":
    b = determine_backend()
    print(b.name)
