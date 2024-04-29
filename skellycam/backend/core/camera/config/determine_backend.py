import enum
import platform

import cv2


class BackendSelection(enum.Enum):
    CAP_ANY = cv2.CAP_ANY
    CAP_DSHOW = cv2.CAP_DSHOW


def determine_backend() -> BackendSelection:
    if platform.system() == "Windows":
        return BackendSelection.CAP_DSHOW
    else:
        return BackendSelection.CAP_ANY


if __name__ == "__main__":
    b = determine_backend()
    print(b.name)
