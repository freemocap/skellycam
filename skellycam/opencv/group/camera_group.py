import logging
import multiprocessing
import time
from typing import Dict, List

from skellycam import CameraConfig
from skellycam.detection.detect_cameras import detect_cameras
from skellycam.opencv.group.strategies.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from skellycam.opencv.group.strategies.strategies import Strategy

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
        self,
        camera_ids_list: List[str] = None,
        strategy: Strategy = Strategy.X_CAM_PER_PROCESS,
        camera_config_dictionary: Dict[str, CameraConfig] = None,
    ):
        logger.info(
            f"Creating camera group for cameras: {camera_ids_list} with strategy {strategy} and camera configs {camera_config_dictionary}"
        )
        self._event_dictionary = None
        self._strategy_enum = strategy
        self._camera_ids = camera_ids_list

        # Make optional, if a list of cams is sent then just use that
        if camera_ids_list is None:
            if camera_config_dictionary is not None:
                camera_ids_list = list(camera_config_dictionary.keys())
            else:
                camera_ids_list = detect_cameras().cameras_found_list

        self._strategy_class = self._resolve_strategy(camera_ids_list)

        if camera_config_dictionary is None:
            logger.info(
                f"No camera config dict passed in, using default config: {CameraConfig()}"
            )
            self._camera_config_dictionary = {}
            for camera_id in camera_ids_list:
                self._camera_config_dictionary[camera_id] = CameraConfig(
                    camera_id=camera_id
                )
        else:
            self._camera_config_dictionary = camera_config_dictionary

    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def exit_event(self):
        return self._exit_event

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def camera_config_dictionary(self):
        return self._camera_config_dictionary

    def update_camera_configs(self, camera_config_dictionary: Dict[str, CameraConfig]):
        logger.info(f"Updating camera configs to {camera_config_dictionary}")
        self._camera_config_dictionary = camera_config_dictionary
        self._strategy_class.update_camera_configs(camera_config_dictionary)

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")
        self._exit_event = multiprocessing.Event()
        self._start_event = multiprocessing.Event()
        self._event_dictionary = {"start": self._start_event, "exit": self._exit_event}
        self._strategy_class.start_capture(
            event_dictionary=self._event_dictionary,
            camera_config_dict=self._camera_config_dictionary,
        )

        self._wait_for_cameras_to_start()

    def _wait_for_cameras_to_start(self, restart_process_if_it_dies: bool = True):
        logger.info(f"Waiting for cameras {self._camera_ids} to start")
        all_cameras_started = False
        while not all_cameras_started:
            time.sleep(0.5)
            camera_started_dictionary = dict.fromkeys(self._camera_ids, False)

            for camera_id in self._camera_ids:
                camera_started_dictionary[camera_id] = self.check_if_camera_is_ready(
                    camera_id
                )

            logger.debug(f"Camera started? {camera_started_dictionary}")

            logger.debug(f"Active processes { multiprocessing.active_children()}")
            if restart_process_if_it_dies:
                self._restart_dead_processes()

            all_cameras_started = all(list(camera_started_dictionary.values()))

        logger.info(f"All cameras {self._camera_ids} started!")
        self._start_event.set()  # start frame capture on all cameras

    def check_if_camera_is_ready(self, cam_id: str):
        return self._strategy_class.check_if_camera_is_ready(cam_id)

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

    def _restart_dead_processes(self):
        active_processes = multiprocessing.active_children()
        active_process_names = [process.name for process in active_processes]
        for process in self._strategy_class.processes:
            if process.name not in active_process_names:
                logger.info(f"Process {process.name} died! Restarting now...")
                process.start_capture(
                    event_dictionary=self._event_dictionary,
                    camera_config_dict=self._camera_config_dictionary,
                )


# async def getall(g: CameraGroup):
#     await asyncio.gather(
#         cam_show("0", lambda: g.get_by_cam_id("0")),
#         cam_show("2", lambda: g.get_by_cam_id("2")),
#     )
#
#
# if __name__ == "__main__":
#     cams = ["0"]
#     g = CameraGroup(cams)
#     g.start()
#
#     asyncio.run(getall(g))
