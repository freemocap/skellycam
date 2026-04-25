import logging
import time
from collections import deque

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.camera_loop_update_checks import camera_loop_update_checks
from skellycam.core.camera.opencv.opencv_helpers.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_helpers.handle_recording_updates import finish_recording
from skellycam.core.camera.opencv.opencv_helpers.handle_video_recording_loop import handle_video_recording
from skellycam.core.camera.opencv.opencv_helpers.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms, wait_10us
from skellycam.core.recorders.videos.video_recorder import VideoRecorder

logger = logging.getLogger(__name__) 

MAX_FAIL_COUNT = 30

def run_opencv_camera_loop(camera_shm: CameraSharedMemoryRingBuffer,
                           config: CameraConfig,
                           cv2_video_capture: cv2.VideoCapture,
                           frame_rec_array: np.recarray,
                           ipc: CameraGroupIPC,
                           orchestrator: CameraOrchestrator,
                           self_status: CameraStatus,
                           update_camera_settings_subscription: TopicSubscriptionQueue,
                           recording_info_subscription: TopicSubscriptionQueue):
    video_recorder: VideoRecorder | None = None
    previous_tik = time.perf_counter_ns()

    number_of_frames_outside_acceptable_range = 0
    fail_count = 0
    frame_durations_seconds= deque(maxlen=1000)
    framerate: float | None = None #median framerate of the past 1000
    try:
        while ipc.should_continue:
            (config,
             frame_rec_array,
             video_recorder,
             self_status,
             ) = camera_loop_update_checks(config=config,
                                           cv2_video_capture=cv2_video_capture,
                                           frame_rec_array=frame_rec_array,
                                           ipc=ipc,
                                           orchestrator=orchestrator,
                                           recording_info_subscription=recording_info_subscription,
                                           self_status=self_status,
                                           update_camera_settings_subscription=update_camera_settings_subscription,
                                           video_recorder=video_recorder,
                                           framerate=framerate
                                           )

            if self_status.should_close.value:
                logger.info(f"Camera {config.camera_id} received shutdown signal.")
                break
            if self_status.is_paused.value:
                wait_1ms()
                continue

            if not orchestrator.should_grab_by_id(camera_id=config.camera_id):
                wait_10us()
                continue
            self_status.grabbing_frame.value = True
            frame_success = False
            while not frame_success and ipc.should_continue and fail_count < MAX_FAIL_COUNT:
                fail_count += 1
                frame_success, frame_rec_array = opencv_get_frame(cap=cv2_video_capture,
                                                                  frame_rec_array=frame_rec_array, )
                if not frame_success:
                    logger.error(f"Failed to grab frame from camera {config.camera_id}. Retrying...")
                    if not cv2_video_capture.isOpened():
                        raise RuntimeError(f"Camera {config.camera_id} shutdown unexpectedly - exiting camera loop.")
                current_tik = time.perf_counter_ns()
                frame_durations_seconds.append((current_tik - previous_tik) / 1e9)
                previous_tik = current_tik
                if len(frame_durations_seconds) >= 30:
                    framerate = 1.0 / np.median(np.array(frame_durations_seconds))

            fail_count = 0
            # NOTE - Get `should_record` flags BEFORE unsetting 'grabbing_frame' to avoid
            # potential race-condition-generating flag setting gaps between cameras
            (should_record_frame,
             should_finish_recording) = orchestrator.should_record_frame_number(
                frame_number=frame_rec_array.frame_metadata.frame_number[0], )

            self_status.grabbing_frame.value = False

            frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = time.perf_counter_ns()
            camera_shm.put_frame(frame_rec_array=frame_rec_array, overwrite=True)
            frame_rec_array.frame_metadata.timestamps.post_copy_to_camera_shm_ns[0] = time.perf_counter_ns()

            video_recorder = handle_video_recording(config=config,
                                                    frame_rec_array=frame_rec_array,
                                                    ipc=ipc,
                                                    self_status=self_status,
                                                    should_finish_recording=should_finish_recording,
                                                    should_record_frame=should_record_frame,
                                                    video_recorder=video_recorder)
            (config,
             cv2_video_capture,
             number_of_frames_outside_acceptable_range) = check_framerate_reset(config=config,
                                                                                cv2_video_capture=cv2_video_capture,
                                                                                frame_rec_array=frame_rec_array,
                                                                                number_of_frames_outside_acceptable_range=number_of_frames_outside_acceptable_range,
                                                                                previous_tik=previous_tik)
            frame_rec_array = initialize_frame_recarray(frame_rec_array=frame_rec_array)

            # Last camera to increment their frame count status triggers the next frame_grab
            self_status.frame_count.value = frame_rec_array.frame_metadata.frame_number[0]
            previous_tik = time.perf_counter_ns()

    except Exception as e:
        self_status.signal_error()
        logger.exception(f"Exception occurred in camera loop for Camera: {config.camera_id} - {e}")
        ipc.kill_everything()
        raise
    finally:
        if video_recorder:
            finish_recording(ipc=ipc, video_recorder=video_recorder)
            logger.warning(f"Camera {config.camera_id} closed mid-recording!"   )
        self_status.connected.value = False
        self_status.closed.value = True
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

    frame_rec_array.frame_metadata.timestamps.initialized_ns[0] = time.perf_counter_ns()

    return frame_rec_array


def check_framerate_reset(config: CameraConfig,
                          cv2_video_capture: cv2.VideoCapture,
                          frame_rec_array: np.recarray,
                          number_of_frames_outside_acceptable_range: int,
                          previous_tik: int) -> tuple[CameraConfig, cv2.VideoCapture, int]:
    #TODO - FIGURE OUT A BETTER WAY TO GET TARGET FPS
    target_frame_duration_ms = (30 ** -1) * 1e3  # Convert framerate to nanoseconds per frame
    max_acceptable_frame_duration_ms = target_frame_duration_ms * 2
    if frame_rec_array.frame_metadata.frame_number[0] > 100:
        frame_duration_ms = (time.perf_counter_ns() - previous_tik) / 1e6  # Convert to milliseconds
        if frame_duration_ms > max_acceptable_frame_duration_ms:
            number_of_frames_outside_acceptable_range += 1
        else:
            number_of_frames_outside_acceptable_range = 0
        if number_of_frames_outside_acceptable_range > 30:
            logger.warning(
                f"Camera {config.camera_id} has had {number_of_frames_outside_acceptable_range} consecutive frames that were longer than acceptable duration ({max_acceptable_frame_duration_ms:.2f}ms) - I'm not sure why this happens, but resetting camera will help, so let's do that. ")
            cv2_video_capture.release()
            cv2_video_capture, config = create_cv2_video_capture(config)
            number_of_frames_outside_acceptable_range = 0
    return config, cv2_video_capture, number_of_frames_outside_acceptable_range
