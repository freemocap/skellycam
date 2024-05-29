import cv2
import numpy as np

from skellycam.core import CameraId
from skellycam.utilities.wait_functions import wait_1ms


class MockVideoCapture:
    def __init__(self, camera_id: CameraId, *args, **kwargs):
        self.camera_id = camera_id
        self.is_opened = True
        self.frame_grabbed = False
        self.properties = {}
        self.read_called_count = 0
        self.grab_called_count = 0  # Track how many times grab is called
        self.retrieve_called_count = 0  # Track how many times retrieve is called
        self.properties[cv2.CAP_PROP_FRAME_HEIGHT] = 480
        self.properties[cv2.CAP_PROP_FRAME_WIDTH] = 640

    def create_fake_image(self) -> np.ndarray:
        wait_1ms()
        return np.random.randint(0,
                                 255,
                                 size=(self.properties[cv2.CAP_PROP_FRAME_HEIGHT],
                                       self.properties[cv2.CAP_PROP_FRAME_WIDTH],
                                       3),
                                 dtype=np.uint8)

    def read(self) -> tuple[bool, np.ndarray]:
        self.read_called_count += 1
        if not self.isOpened():
            return False, None
        return True, self.create_fake_image()

    def grab(self) -> bool:
        self.grab_called_count += 1
        if not self.isOpened():
            return False
        self.frame_grabbed = True
        return True

    def retrieve(self) -> tuple[bool, np.ndarray]:
        self.retrieve_called_count += 1
        if not self.isOpened():
            return False, None
        if self.frame_grabbed:
            self.frame_grabbed = False
            return True, self.create_fake_image()
        else:
            return False, None

    def release(self) -> None:
        self.is_opened = False

    def isOpened(self) -> bool:
        return self.is_opened

    def set(self, prop_id: int, value: float) -> bool:
        self.properties[prop_id] = value
        return True

    def get(self, prop_id: int) -> float:
        return float(self.properties.get(prop_id, 0.0))

    def __del__(self):
        self.release()
