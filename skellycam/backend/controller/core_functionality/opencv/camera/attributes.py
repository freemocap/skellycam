class Attributes:
    def __init__(self, cv2_capture):
        self._cv2_capture = cv2_capture

    @property
    def image_width(self):
        return int(self._cv2_capture.get(3))

    @property
    def image_height(self):
        return int(self._cv2_capture.get(4))
