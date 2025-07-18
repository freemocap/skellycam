import time

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.check_for_new_config import check_for_new_config
from skellycam.core.camera.opencv.opencv_helpers.check_for_new_recording_info import check_for_new_recording_info, \
    finish_recording
from skellycam.core.camera.opencv.opencv_helpers.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator, CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import RecordingFinishedMessage
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms, wait_10us

import logging
logger = logging.getLogger(__name__)

def run_opencv_camera_loop(camera_shm: FramePayloadSharedMemoryRingBuffer,
                           config: CameraConfig,
                           cv2_video_capture: cv2.VideoCapture,
                           frame_rec_array: np.recarray,
                           ipc: CameraGroupIPC,
                           orchestrator: CameraOrchestrator,
                           self_status: CameraStatus,
                           update_camera_settings_subscription: TopicSubscriptionQueue,
                           recording_info_subscription: TopicSubscriptionQueue):
    video_recorder: VideoRecorder | None = None
    try:
        while ipc.should_continue:

            video_recorder = check_for_new_recording_info(config=config,
                                                          ipc=ipc,
                                                          orchestrator=orchestrator,
                                                          recording_info_subscription=recording_info_subscription,
                                                          self_status=self_status,
                                                          video_recorder=video_recorder)
            frame_rec_array, config = check_for_new_config(current_config=config,
                                                           frame_rec_array=frame_rec_array,
                                                           cv2_video_capture=cv2_video_capture,
                                                           ipc=ipc,
                                                           self_status=self_status,
                                                           update_camera_settings_subscription=update_camera_settings_subscription)

            if ipc.should_pause.value:
                if not self_status.is_paused.value:
                    logger.trace(f"Pausing camera {config.camera_id}...")
                    self_status.is_paused.value = True
                wait_1ms()
                continue
            self_status.is_paused.value = False

            if not orchestrator.should_grab_by_id(camera_id=config.camera_id):
                wait_10us()
                continue


            self_status.grabbing_frame.value = True
            frame_rec_array = opencv_get_frame(cap=cv2_video_capture,
                                               frame_rec_array=frame_rec_array, )

            # get `should_record` bool BEFORE unsetting 'grabbing_frame' to avoid gaps between cameras
            should_record_frame, should_finish_recording = orchestrator.should_record_frame_number(
                frame_number=frame_rec_array.frame_metadata.frame_number[0], )

            self_status.grabbing_frame.value = False

            while orchestrator.any_grabbing_frame and ipc.should_continue:
                # Wait for all cameras to finish grabbing frames
                wait_10us()

            if should_record_frame:
                if video_recorder is None:
                    raise RuntimeError("Record requested before video_recorder was created.")
                self_status.is_recording_frame.value = True
                frame_rec_array.frame_metadata.timestamps.pre_frame_record_ns[0] = time.perf_counter_ns()
                video_recorder.record_frame(frame=frame_rec_array)
                frame_rec_array.frame_metadata.timestamps.post_frame_record_ns[0] = time.perf_counter_ns()
                self_status.is_recording_frame.value = False
            if should_finish_recording and video_recorder is not None:
                if not self_status.recording_in_progress.value:
                    raise RuntimeError(
                        f"Finish recording requested but no recording in progress for camera {config.camera_id}.")
                if video_recorder is None or not video_recorder.any_data_saved:
                    raise RuntimeError(
                        f"Recording in progress but no video_recorder or no data saved for camera {config.camera_id}.")
                logger.info(f"Camera {config.camera_id} finishing and closing video recorder...")
                finish_recording(ipc=ipc,video_recorder=video_recorder)
                video_recorder = None
                self_status.recording_in_progress.value = False

            frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = time.perf_counter_ns()
            camera_shm.put_frame(frame_rec_array=frame_rec_array, overwrite=True)
            frame_rec_array.frame_metadata.timestamps.post_copy_to_camera_shm_ns[0] = time.perf_counter_ns()

            frame_rec_array = initialize_frame_recarray(frame_rec_array=frame_rec_array)

            # Last camera to increment their frame count status triggers the next frame_grab
            self_status.frame_count.value = frame_rec_array.frame_metadata.frame_number[0]

    except Exception as e:
        self_status.signal_error()
        logger.exception(f"Exception occurred in camera loop for Camera: {config.camera_id} - {e}")
        ipc.kill_everything()
        raise
    finally:
        self_status.running.value = False
        logger.debug(f"Camera {config.camera_id} loop ended.")




def initialize_frame_recarray(frame_rec_array: np.recarray) -> np.recarray:
    """Initialize timestamps for a new frame"""
    # Reset all timestamps to 0
    frame_rec_array.frame_metadata.timestamps.pre_frame_grab_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_frame_grab_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_frame_retrieve_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_frame_retrieve_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_frame_record_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_frame_record_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_copy_to_camera_shm_ns[0] = 0

    frame_rec_array.frame_metadata.timestamps.frame_initialized_ns[0] = time.perf_counter_ns()

    return frame_rec_array
