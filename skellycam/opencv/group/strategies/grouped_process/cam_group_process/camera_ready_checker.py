import multiprocessing
from typing import List


class CameraReadyChecker:
    """
    Only to be used with CamGroupProcess.
    """

    def __init__(self, camera_ids: List[str]):
        self._manager = multiprocessing.Manager()
        self._cam_ready = self._manager.dict()
        for cam in camera_ids:
            self._cam_ready[cam] = False

    @property
    def cam_ready_ipc(self):
        return self._cam_ready

    @property
    def is_cam_ready_by_id(self, cam_id: str):
        return self._cam_ready[cam_id]

    def all_ready(self):
        for value in self._cam_ready.values():
            if not value:
                return False
        return True
