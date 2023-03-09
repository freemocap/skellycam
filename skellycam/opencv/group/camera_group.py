import logging
import multiprocessing
import time
from pathlib import Path
from typing import Dict, List, Union

from PyQt6.QtCore import pyqtSignal

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from skellycam.opencv.group.strategies.strategies import Strategy
from skellycam.opencv.video_recorder.video_save_background_process.video_save_background_process import \
    VideoSaveBackgroundProcess

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            camera_ids_list: List[str],
            camera_configs: Dict[str, CameraConfig],
            strategy: Strategy = Strategy.X_CAM_PER_PROCESS,

    ):
        self._dump_frames_to_video_event = multiprocessing.Event()
        logger.info(
            f"Creating camera group for cameras: {camera_ids_list} with strategy {strategy} and camera configs {camera_configs}"
        )
        self._event_dictionary = None
        self._strategy_enum = strategy
        self._camera_ids = camera_ids_list
        self._camera_configs = camera_configs

        self._strategy_class = self._resolve_strategy(camera_ids=self._camera_ids,
                                                      camera_configs=self._camera_configs,
                                                      )


    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def exit_event(self):
        return self._exit_event

    @property
    def should_record_frames_event(self) -> multiprocessing.Event:
        return self._should_record_frames_event

    @property
    def dump_frames_to_video_event(self) -> multiprocessing.Event:
        return self._dump_frames_to_video_event

    @property
    def camera_ids(self):
        return self._camera_ids


    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        return self._strategy_class.latest_frames

    def set_folder_to_record_videos(self, path: Union[str, Path]):
        logger.info(f"Setting folder to record videos to {path}")
        self._strategy_class.folder_to_save_videos = str(path)

    def ensure_video_save_process_running(self):
        if not self._video_save_background_process.is_alive:
            self._start_video_save_background_process()

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")
        self._exit_event = multiprocessing.Event()
        self._start_event = multiprocessing.Event()
        self._should_record_frames_event = multiprocessing.Event()

        self._event_dictionary = {"start": self._start_event,
                                  "exit": self._exit_event,
                                  "should_record_frames": self._should_record_frames_event}
        self._strategy_class.start_capture(
            event_dictionary=self._event_dictionary,

        )

        self._start_video_save_background_process()

        self._wait_for_cameras_to_start()

    def get_latest_frame_by_camera_id(self, camera_id: str):
        return self._strategy_class.latest_frames[camera_id]

    def _resolve_strategy(self, camera_ids: List[str], camera_configs: Dict[str, CameraConfig]):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(camera_ids = camera_ids,
                                          camera_configs = camera_configs,)

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

            logger.debug(f"Active processes {multiprocessing.active_children()}")
            if restart_process_if_it_dies:
                self._restart_dead_processes()

            all_cameras_started = all(list(camera_started_dictionary.values()))

        logger.info(f"All cameras {self._camera_ids} started!")
        self._start_event.set()  # start frame capture on all cameras

    def check_if_camera_is_ready(self, cam_id: str):
        return self._strategy_class.check_if_camera_is_ready(cam_id)

    def close(self, wait_for_exit: bool = True, cameras_closed_signal: pyqtSignal = None):
        logger.info("Closing camera group")
        self._set_exit_event()
        self._terminate_processes()

        if wait_for_exit:
            while self.is_capturing:
                logger.debug("waiting for camera group to stop....")
                time.sleep(0.1)
        if cameras_closed_signal is not None:
            cameras_closed_signal.emit()

    def _set_exit_event(self):
        logger.info("Setting exit event")
        self.exit_event.set()

    def _terminate_processes(self):
        logger.info("Terminating processes")
        for cam_group_process in self._strategy_class._processes:
            logger.info(f"Terminating process - {cam_group_process.name}")
            cam_group_process.terminate()

        logger.info("Terminating VideoSaveBackgroundProcess")
        self._video_save_background_process.terminate()

    def _restart_dead_processes(self):
        active_processes = multiprocessing.active_children()
        active_process_names = [process.name for process in active_processes]
        for process in self._strategy_class.processes:
            if process.name not in active_process_names:
                logger.info(f"Process {process.name} died! Restarting now...")
                process.start_capture(
                    event_dictionary=self._event_dictionary,
                    camera_configs=self._camera_configs,
                )

    def _start_video_save_background_process(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._video_save_background_process = VideoSaveBackgroundProcess(
            frame_lists_by_camera=self._strategy_class.frame_lists_by_camera,
            folder_to_save_videos=self._strategy_class.folder_to_save_videos,
            dump_frames_to_video_event=self._dump_frames_to_video_event, )
        self._video_save_background_process.start()

    def update_camera_configs(self, camera_configs: Dict[str, CameraConfig]):
        logger.info(f"Updating camera configs to {camera_configs} - old configs were: {self._camera_configs}")
        self._camera_configs = camera_configs
        self._strategy_class.update_camera_configs(self._camera_configs)

# async def getall(g: CameraGroup):
#     await asyncio.gather(
#         cam_show("0", lambda: g.get_latest_frame_by_camera_id("0")),
#         cam_show("2", lambda: g.get_latest_frame_by_camera_id("2")),
#     )
#
#
# if __name__ == "__main__":
#     cams = ["0"]
#     g = CameraGroup(cams)
#     g.start()
#
#     asyncio.run(getall(g))
