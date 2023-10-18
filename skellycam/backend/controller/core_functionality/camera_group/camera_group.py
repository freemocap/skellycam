import multiprocessing
import time
from typing import Dict

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.strategies.grouped_process_strategy import \
    GroupedProcessStrategy
from skellycam.backend.controller.core_functionality.camera_group.strategies.strategies import Strategy
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.frame_payload import FramePayload


class CameraGroup:
    def __init__(
            self,
            camera_configs: Dict[str, CameraConfig],
            strategy: Strategy = Strategy.X_CAM_PER_PROCESS,
    ):
        self._start_event = None
        self._exit_event = None
        logger.info(
            f"Creating camera group with strategy {strategy} and camera configs {camera_configs}"
        )
        self._event_dictionary = None
        self._strategy_enum = strategy
        self._camera_configs = camera_configs
        self._strategy_class = self._resolve_strategy()

    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def exit_event(self):
        return self._exit_event

    @property
    def queue_size(self) -> Dict[str, int]:
        return self._strategy_class.queue_size

    def update_configs(self, camera_configs: Dict[str, CameraConfig]):
        logger.info(f"Updating camera configs to {camera_configs}")
        self._camera_configs = camera_configs
        self._strategy_class.update_camera_configs(camera_configs)

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")
        self._exit_event = multiprocessing.Event()
        self._start_event = multiprocessing.Event()
        self._event_dictionary = {"start": self._start_event,
                                  "exit": self._exit_event}
        self._strategy_class.start_capture(
            event_dictionary=self._event_dictionary,
        )

        self._wait_for_cameras_to_start()

    def _wait_for_cameras_to_start(self, restart_process_if_it_dies: bool = True):
        logger.trace(f"Waiting for cameras {self._camera_configs.keys()} to start")
        all_cameras_started = False
        while not all_cameras_started:
            time.sleep(0.5)
            camera_started_dictionary = dict.fromkeys(self._camera_configs.keys(), False)

            for camera_id in self._camera_configs.keys():
                camera_started_dictionary[camera_id] = self.check_if_camera_is_ready(
                    camera_id
                )

            logger.trace(f"Camera started? {camera_started_dictionary}")

            logger.trace(f"Active processes {multiprocessing.active_children()}")
            if restart_process_if_it_dies:
                self._restart_dead_processes()

            all_cameras_started = all(list(camera_started_dictionary.values()))

        logger.success(f"All cameras {self._camera_configs.keys()} started!")
        self._start_event.set()  # start frame capture on all cameras

    def check_if_camera_is_ready(self, cam_id: str):
        return self._strategy_class.check_if_camera_is_ready(cam_id)

    def get_by_cam_id(self, cam_id: str):
        return self._strategy_class.get_current_frame_by_cam_id(cam_id)

    def latest_frames(self) -> Dict[str, FramePayload]:
        return self._strategy_class.get_latest_frames()

    def _resolve_strategy(self):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(camera_configs=self._camera_configs)

    def close(self, wait_for_exit: bool = True):
        logger.info("Closing camera group")
        self._set_exit_event()
        # self._terminate_processes()

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
                )
