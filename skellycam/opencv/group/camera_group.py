import logging
import multiprocessing
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from PyQt6.QtCore import pyqtSignal

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from skellycam.opencv.group.strategies.strategies import Strategy
from skellycam.opencv.group.wait_for_all_cameras import StartSynchronizer, WaitArgs
from skellycam.opencv.video_recorder.video_save_background_process.video_save_background_process import (
    VideoSaveBackgroundProcess,
)
from skellycam.viewers.cv_cam_viewer import CvCamViewer

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
        self,
        camera_ids_list: List[str],
        camera_configs: Optional[Dict[str, CameraConfig]] = None,
        strategy: Strategy = Strategy.X_CAM_PER_PROCESS,
    ):
        self._dump_frames_to_video_event = multiprocessing.Event()
        self._camera_configs = camera_configs
        if camera_configs:
            logger.info(
                f"Creating camera group for cameras: {camera_ids_list} with strategy {strategy} and camera configs {camera_configs}"
            )

        self._event_dictionary = None
        self._strategy_enum = strategy
        self._camera_ids = camera_ids_list

        self._strategy_class = self._resolve_strategy(
            camera_ids=self._camera_ids,
            camera_configs=self._camera_configs,
        )
        self._start_sync = StartSynchronizer(self._strategy_class)

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

    def close(
        self, wait_for_exit: bool = True, cameras_closed_signal: pyqtSignal = None
    ):
        logger.info("Closing camera group")
        self._set_exit_event()
        self._terminate_processes()

        if wait_for_exit:
            while self.is_capturing:
                logger.debug("waiting for camera group to stop....")
                time.sleep(0.1)
        if cameras_closed_signal is not None:
            cameras_closed_signal.emit()

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")
        self._exit_event = multiprocessing.Event()
        self._start_event = multiprocessing.Event()
        self._should_record_frames_event = multiprocessing.Event()

        self._event_dictionary = {
            "start": self._start_event,
            "exit": self._exit_event,
            "should_record_frames": self._should_record_frames_event,
        }
        self._strategy_class.start_capture(
            event_dictionary=self._event_dictionary,
        )

        self._start_video_save_background_process()

        self._start_sync.wait_for_cameras_to_start(
            WaitArgs(camera_ids=self._camera_ids)
        )
        logger.info(f"All cameras {self._camera_ids} started!")

    def get_latest_frame_by_camera_id(self, camera_id: str):
        return self._strategy_class.latest_frames_by_camera_id(camera_id)

    def _resolve_strategy(
        self, camera_ids: List[str], camera_configs: Dict[str, CameraConfig]
    ):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(
                camera_ids=camera_ids,
                camera_configs=camera_configs,
            )

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

    def _start_video_save_background_process(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._video_save_background_process = VideoSaveBackgroundProcess(
            frame_lists_by_camera=self._strategy_class.frame_lists_by_camera,
            folder_to_save_videos=self._strategy_class.folder_to_save_videos,
            dump_frames_to_video_event=self._dump_frames_to_video_event,
        )
        self._video_save_background_process.start()

    def update_camera_configs(self, camera_configs: Dict[str, CameraConfig]):
        logger.info(
            f"Updating camera configs to {camera_configs} - old configs were: {self._camera_configs}"
        )
        self._camera_configs = camera_configs
        self._strategy_class.update_camera_configs(self._camera_configs)


if __name__ == "__main__":
    cams = ["0"]
    g = CameraGroup(cams)
    g.start()
    viewer = CvCamViewer()
    viewer.begin_viewer("0")

    while True:
        time.sleep(0.001)
        frame = g.get_latest_frame_by_camera_id("0")
        viewer.recv_img(frame)
