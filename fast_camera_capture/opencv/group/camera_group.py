import asyncio
import logging
import multiprocessing
import time
from typing import List

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.experiments.cam_show import cam_show
from fast_camera_capture.opencv.group.strategies.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from fast_camera_capture.opencv.group.strategies.strategies import Strategy

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
        self, cam_ids: List[str], strategy: Strategy = Strategy.X_CAM_PER_PROCESS
    ):
        self._strategy_enum = strategy
        self._cam_ids = cam_ids
        # Make optional, if a list of cams is sent then just use that
        if not cam_ids:
            _cams = detect_cameras()
            cam_ids = _cams.cameras_found_list
        self._strategy_class = self._resolve_strategy(cam_ids)

    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def exit_event(self):
        return self._exit_event

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        self._exit_event = multiprocessing.Event()
        self._strategy_class.start_capture(self.exit_event)

        self._wait_for_cameras_to_start()

    def _wait_for_cameras_to_start(self):
        logger.info(f"Waiting for cameras {self._cam_ids} to start")
        all_cameras_started = False
        while not all_cameras_started:
            time.sleep(0.5)
            camera_started_dictionary = dict.fromkeys(self._cam_ids, False)
            for camera_id in self._cam_ids:
                camera_started_dictionary[camera_id] = (
                    self.get_by_cam_id(camera_id) is not None
                )
            logger.debug(f"Camera started? {camera_started_dictionary}")
            all_cameras_started = all(list(camera_started_dictionary.values()))

        logger.info(f"All cameras {self._cam_ids} started!")

    def get_by_cam_id(self, cam_id: str):
        return self._strategy_class.get_by_cam_id(cam_id)

    def latest_frames(self):
        return self._strategy_class.get_latest_frames()

    def _resolve_strategy(self, cam_ids: List[str]):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(cam_ids)

    def close(self, wait_for_exit: bool = True):
        logger.info("Closing camera group")
        self._set_exit_event()
        self._terminate_processes()

        if wait_for_exit:
            while self.is_capturing:
                logger.debug("waiting for camera group to stop....")
                time.sleep(0.1)

    def _set_exit_event(self):
        logger.info("Setting exit event")
        self.exit_event.set()

    def _terminate_processes(self):
        logger.info("Terminating processes")
        for cam_group_process in self._strategy_class._processes:
            logger.info(f"Terminating process - {cam_group_process.name}")
            cam_group_process.terminate()


async def getall(g: CameraGroup):
    await asyncio.gather(
        cam_show("0", lambda: g.get_by_cam_id("0")),
        cam_show("2", lambda: g.get_by_cam_id("2")),
    )


if __name__ == "__main__":
    cams = ["0"]
    g = CameraGroup(cams)
    g.start()

    asyncio.run(getall(g))
