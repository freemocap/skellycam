import time

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.handle_recording_updates import finish_recording
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraStatus
from skellycam.core.recorders.videos.video_recorder import VideoRecorder

import logging
logger = logging.getLogger(__name__)
 
def handle_video_recording(config: CameraConfig,
                           frame_rec_array: np.recarray,
                           ipc: CameraGroupIPC,
                           self_status: CameraStatus,
                           should_finish_recording: bool,
                           should_record_frame: bool,
                           video_recorder: VideoRecorder | None) -> VideoRecorder | None:
    if should_record_frame:
        if video_recorder is None:
            raise RuntimeError("Record requested before video_recorder was created.")
        self_status.is_recording_frame.value = True
        video_recorder.record_frame(frame=frame_rec_array)
        self_status.is_recording_frame.value = False

    if should_finish_recording and video_recorder is not None:
        if not self_status.recording_in_progress.value:
            raise RuntimeError("Finish recording requested but no recording in progress for camera", config.camera_id)
        if video_recorder is None or not video_recorder.any_data_saved:
            raise RuntimeError("Recording in progress but no video_recorder or no data saved for camera",
                               config.camera_id)
        logger.info(f"Camera {config.camera_id} finishing and closing video recorder...")
        finish_recording(ipc=ipc, video_recorder=video_recorder)
        video_recorder = None
        self_status.recording_in_progress.value = False
    return video_recorder
