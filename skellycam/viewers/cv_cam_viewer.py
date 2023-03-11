import multiprocessing
from multiprocessing import Process
from typing import Optional

import cv2
from setproctitle import setproctitle

from skellycam.detection.models.frame_payload import FramePayload


class CvCamViewer:
    def __init__(self):
        self._process: Optional[Process] = None
        self._manager = multiprocessing.Manager()
        self._value = self._manager.dict()

    def begin_viewer(self, cam_id: str):
        name = f"Python - Imshow - Camera {cam_id}"
        self._process = Process(
            name=name,
            target=_begin,
            args=(self._value, cam_id, name),
        )
        self._process.start()

    def recv_img(self, frame_payload: FramePayload):
        if frame_payload and frame_payload.success:
            self._value["frame"] = frame_payload


def _begin(shared_value, cam_id, name):
    setproctitle(name)
    while True:
        if cv2.waitKey(1) == 27:
            cv2.destroyAllWindows()
            break
        if "frame" not in shared_value:
            continue
        payload = shared_value["frame"]
        cv2.imshow(str(cam_id), payload.image)
