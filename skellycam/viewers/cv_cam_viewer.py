import multiprocessing
import time
from multiprocessing import Process
from typing import Union

import cv2
from setproctitle import setproctitle

from skellycam.detection.models.frame_payload import FramePayload


class CvCamViewer:
    def __init__(self):
        self._process: Process = None
        self._payload = None
        self._manager = multiprocessing.Manager()
        self._value = self._manager.dict()

    def begin_viewer(self, cam_id: str):
        self._process = Process(target=_begin, args=(self._value, cam_id))
        self._process.start()

    def recv_img(self, frame_payload: FramePayload):
        if frame_payload and frame_payload.success:
            self._value["frame"] = frame_payload


def _begin(shared_value, cam_id):
    setproctitle(f"Viewer {cam_id}")
    while True:
        if cv2.waitKey(1) == 27:
            cv2.destroyAllWindows()
            break
        if "frame" not in shared_value:
            continue
        payload = shared_value["frame"]
        cv2.imshow(str(cam_id), payload.image)
