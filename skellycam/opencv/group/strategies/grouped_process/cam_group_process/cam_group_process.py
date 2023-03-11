import logging
import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import Dict, List, Optional

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.camera_ready_checker import (
    CameraReadyChecker,
)
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.internal_capture_process import (
    InternalCaptureProcess,
)

logger = logging.getLogger(__name__)


class CamGroupProcess:
    def __init__(
        self,
        camera_ids: List[str],
        frame_repository: Dict[str, List[FramePayload]] = None,
    ):
        if len(camera_ids) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._camera_ids = camera_ids
        self._frame_repository = frame_repository or self._create_frame_watcher()

        assert all(
            [camera_id in self._frame_repository.keys() for camera_id in camera_ids]
        ), "We should only have frame lists for cameras in this group"

        self._cam_ready_manager = CameraReadyChecker(camera_ids)
        self._process: Optional[Process] = None
        self._payload = None

    """
    CORE API
    """

    def start_capture(self):
        """
        Start capturing frames. Only return after we're capturing frames.
        :return:
        """

        logger.info(f"Starting capture `Process` for {self._camera_ids}")
        self._process = InternalCaptureProcess(
            name=f"Python - InternalCaptureProcess - Cameras {self._camera_ids}",
            args=(
                self._camera_ids,
                self._frame_repository,
                self._cam_ready_manager.cam_ready_ipc,
            ),
        )
        self._process.start()

        while not self.is_capturing:
            sleep(0.25)

        logger.debug(f"{self._camera_ids} are now capturing frames.")

    def get_latest_frame_by_camera(self, cam_id: str):
        if self._frame_repository[cam_id]:
            return self._frame_repository[cam_id][-1]

    def check_if_all_cameras_are_ready(self):
        return self._cam_ready_manager.all_ready()

    def is_camera_ready(self, cam_id: str):
        return self._cam_ready_manager.is_cam_ready_by_id(cam_id)

    def stop(self):
        if not self._process:
            return

        self._process.terminate()
        logger.info(f"CamGroupProcess {self.name} terminate command executed")

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def name(self):
        return self._process.name

    @property
    def is_capturing(self):
        if not self._process:
            return False
        if not self._process.is_alive():
            return False
        return self.check_if_all_cameras_are_ready()

    def _create_frame_watcher(self):
        self._frame_repo_manager = multiprocessing.Manager()
        v = self._frame_repo_manager.dict()
        for cam in self.camera_ids:
            v[cam] = self._frame_repo_manager.list()
        return v


if __name__ == "__main__":
    p = CamGroupProcess(camera_ids=["0"])
    p.start_capture()

    while True:
        curr = perf_counter_ns() * 1e-6
        frame = p.get_latest_frame_by_camera("0")
        if frame:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            # print(f"{frame_count_in_ms}ms for this frame")
