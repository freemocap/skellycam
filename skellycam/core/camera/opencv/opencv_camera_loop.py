import logging
import time

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.camera_loop_update_checks import camera_loop_update_checks
from skellycam.core.camera.opencv.opencv_helpers.handle_video_recording_loop import handle_video_recording
from skellycam.core.camera.opencv.opencv_helpers.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator, CameraStatus
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms, wait_10us

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
    previous_tik = time.perf_counter_ns()
    try:
        while ipc.should_continue:

            (config,
             frame_rec_array,
             video_recorder,
             self_status) = camera_loop_update_checks(config=config,
                                                      cv2_video_capture=cv2_video_capture,
                                                      frame_rec_array=frame_rec_array,
                                                      ipc=ipc,
                                                      orchestrator=orchestrator,
                                                      recording_info_subscription=recording_info_subscription,
                                                      self_status=self_status,
                                                      update_camera_settings_subscription=update_camera_settings_subscription,
                                                      video_recorder=video_recorder)
            # print(f"Camera {config.camera_id} loop UPDATE CHECKS took {(time.perf_counter_ns() - og_tik)/1e6} ms for update checks")
            tik = time.perf_counter_ns()
            if self_status.is_paused.value:
                wait_1ms()
                continue

#             # print("Camera {config.camera_id} loop PAUSE CHECK took {(time.perf_counter_ns() - tik)/1e6} ms for pause check")
            if not orchestrator.should_grab_by_id(camera_id=config.camera_id):
                wait_10us()
                continue
            tik = time.perf_counter_ns()
#             print(f"Camera {config.camera_id} loop GRAB CHECK took {(time.perf_counter_ns() - tik)/1e6} ms for grab check")
            tik = time.perf_counter_ns()
            self_status.grabbing_frame.value = True
            frame_rec_array = opencv_get_frame(cap=cv2_video_capture,
                                               frame_rec_array=frame_rec_array, )
#             print(f"Camera {config.camera_id} loop GET FRAME took {(time.perf_counter_ns() - tik)/1e6} ms for frame grab")
            # NOTE - Get `should_record` flags BEFORE unsetting 'grabbing_frame' to avoid
            # potential race-condition-generating flag setting gaps between cameras
            tik = time.perf_counter_ns()
            (should_record_frame,
             should_finish_recording) = orchestrator.should_record_frame_number(
                frame_number=frame_rec_array.frame_metadata.frame_number[0], )
#             print(f"Camera {config.camera_id} loop SHOULD RECORD CHECK took {(time.perf_counter_ns() - tik)/1e6} ms for should record check")

            self_status.grabbing_frame.value = False

            ## Uncomment to adjust logic so each camera waits for all cameras to finish grabbing frames before continuing to shared memory and video recording steps
            # while orchestrator.any_grabbing_frame and ipc.should_continue:
            #     # Wait for all cameras to finish grabbing frames
            #     wait_10us()
            tik = time.perf_counter_ns()
            frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = time.perf_counter_ns()
            camera_shm.put_frame(frame_rec_array=frame_rec_array, overwrite=True)
            frame_rec_array.frame_metadata.timestamps.post_copy_to_camera_shm_ns[0] = time.perf_counter_ns()
#             print(f"Camera {config.camera_id} loop COPY TO SHM took {(time.perf_counter_ns() - tik)/1e6} ms for copy to shared memory")
            video_recorder = handle_video_recording(config=config,
                                                    frame_rec_array=frame_rec_array,
                                                    ipc=ipc,
                                                    self_status=self_status,
                                                    should_finish_recording=should_finish_recording,
                                                    should_record_frame=should_record_frame,
                                                    video_recorder=video_recorder)


            frame_rec_array = initialize_frame_recarray(frame_rec_array=frame_rec_array)

            # Last camera to increment their frame count status triggers the next frame_grab
            self_status.frame_count.value = frame_rec_array.frame_metadata.frame_number[0]
            # tik = time.perf_counter_ns()
            # print(f"Camera {config.camera_id} loop took {(tik - previous_tik) / 1e6} ms for full loop iteration")
            # previous_tik = tik


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
