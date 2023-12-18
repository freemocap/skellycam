import threading
import time
from typing import Dict, Optional, List

import cv2

from skellycam.backend.controller.core_functionality.camera_group.camera_group import CameraGroup
from skellycam.backend.controller.core_functionality.camera_group.video_recorder.video_recorder_manager import \
    VideoRecorderManager
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload, MultiFramePayload
from skellycam.system.environment.get_logger import logger


class CameraGroupManager:

    def __init__(self,
                 frontend_frame_pipe_sender  # multiprocessing.connection.Connection
                 ) -> None:

        self.frontend_frame_pipe_sender = frontend_frame_pipe_sender
        self._camera_group: Optional[CameraGroup] = None
        self._video_recorder_manager: Optional[VideoRecorderManager] = None
        self._camera_runner_thread: Optional[threading.Thread] = None
        self._camera_configs: Optional[Dict[CameraId, CameraConfig]] = None
        self._is_recording = False
        self._stop_recording = False

    def start_recording(self):
        logger.debug(f"Starting recording...")
        if self._video_recorder_manager is not None:
            raise AssertionError("Video recorder manager already initialized! "
                                 "There's a buggo in the application logic somewhere")
        self._video_recorder_manager = VideoRecorderManager(camera_configs=self._camera_configs)
        self._video_recorder_manager.start_recording(
            start_time_perf_counter_ns_to_unix_mapping=(time.perf_counter_ns(), time.time_ns()))
        self._is_recording = True
        self._stop_recording = False

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        if self._video_recorder_manager is None:
            raise AssertionError("Video recorder manager isn't initialized, but `StopRecordingInteraction` was called! "
                                 "There's a buggo in the application logic somewhere")
        self._video_recorder_manager.stop_recording()
        self._stop_recording = True

    def _run_camera_group_loop(self):
        self._camera_group.start()
        multi_frame_payload = MultiFramePayload.create(camera_ids=list(self._camera_configs.keys()))
        while self._camera_group.any_capturing:
            new_frames = self._camera_group.get_new_frames()
            if len(new_frames) > 0:
                multi_frame_payload = self._handle_new_frames(multi_frame_payload, new_frames)
            elif self._is_recording:
                if self._video_recorder_manager is None:
                    logger.error(f"Video recorder manager not initialized")
                    raise AssertionError("Video recorder manager not initialized but `_is_recording` is True")
                if self._video_recorder_manager.has_frames_to_save:
                    self._video_recorder_manager.one_frame_to_disk()
                else:
                    if self._stop_recording:
                        logger.debug(
                            f"No more frames to save, and `_stop_recording` is True - closing video recorder manager")
                        self._close_video_recorder_manager()
            else:
                time.sleep(0.001)

    def _close_video_recorder_manager(self):
        self._video_recorder_manager.finish_and_close()
        while not self._video_recorder_manager.finished:
            time.sleep(0.001)
        self._video_recorder_manager = None
        self._is_recording = False

    def _handle_new_frames(self,
                           multi_frame_payload: MultiFramePayload,
                           new_frames: List[FramePayload]) -> MultiFramePayload:
        for frame in new_frames:
            multi_frame_payload.add_frame(frame=frame)
            if multi_frame_payload.full:
                if self._is_recording:
                    if self._video_recorder_manager is None:
                        logger.error(f"Video recorder manager not initialized")
                        raise AssertionError("Video recorder manager not initialized but `_is_recording` is True")
                    self._video_recorder_manager.handle_multi_frame_payload(multi_frame_payload=multi_frame_payload)

                frontend_payload = self._prepare_frontend_payload(multi_frame_payload=multi_frame_payload)
                self.frontend_frame_pipe_sender.send_bytes(frontend_payload.to_bytes())
                multi_frame_payload = MultiFramePayload.create(camera_ids=list(self._camera_configs.keys()))
        return multi_frame_payload

    def start(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.debug(f"Starting camera group thread...")
        self._camera_configs = camera_configs
        self._camera_group = CameraGroup(camera_configs=self._camera_configs)
        self._camera_runner_thread = threading.Thread(target=self._run_camera_group_loop, daemon=True)
        self._camera_runner_thread.start()

    def close(self):
        logger.debug(f"Stopping camera group thread...")

        self._camera_group.close()
        # self._video_recorder_manager.finish_and_close()
        self._camera_runner_thread.join()

    def update_configs(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.debug(f"Updating camera configs to {camera_configs.keys()}")
        self._camera_configs = camera_configs
        self._camera_group.update_configs(camera_configs=camera_configs)

    def _prepare_frontend_payload(self, multi_frame_payload: MultiFramePayload,
                                  scale_images: float = 0.5) -> MultiFramePayload:
        frontend_payload = multi_frame_payload.copy(deep=True)
        frontend_payload.resize(scale_factor=scale_images)
        for frame in frontend_payload.frames.values():
            frame.set_image(image=cv2.cvtColor(frame.get_image(), cv2.COLOR_BGR2RGB))
        return frontend_payload
