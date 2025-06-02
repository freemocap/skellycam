import logging
import multiprocessing
from copy import deepcopy

import cv2

from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_apply_config import apply_camera_configuration
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBufferDTO, \
    FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


def opencv_camera_run_process(camera_id: CameraIdString,
                              ipc: CameraGroupIPC,
                              orchestrator: CameraGroupOrchestrator,
                              camera_shm_dto: FramePayloadSharedMemoryRingBufferDTO,
                              close_self_flag: multiprocessing.Value,
                              ws_queue: multiprocessing.Queue,
                              ludacris_speed: bool,
                              ):
    # Configure logging in the child process
    from skellycam.system.logging_configuration.configure_logging import configure_logging
    from skellycam import LOG_LEVEL
    configure_logging(LOG_LEVEL, ws_queue=ws_queue)

    camera_config = deepcopy(ipc.camera_configs[camera_id])
    camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                             read_only=False)
    logger.debug(f"Camera {camera_id} shared memory re-created in CameraProcess for camera {camera_id}")

    def should_continue():
        return ipc.should_continue and not close_self_flag.value

    # Check for configuration updates

    cv2_video_capture: cv2.VideoCapture | None = None
    try:
        cv2_video_capture = create_cv2_video_capture(camera_config)

        logger.trace(f"Camera {camera_id} process started")
        camera_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                   config=camera_config,
                                                   initial=True)
        ipc.set_config_by_id(camera_id=camera_id,
                             camera_config=camera_config, )

        logger.info(f"Camera {camera_config.camera_id} ready!")


        # Trigger listening loop
        while should_continue():

            frame_tab = f"Fr# {orchestrator.camera_frame_count[camera_id].value+1}: "
            # print(f"{frame_tab }Camera {camera_id} loop START")
            frame_metadata = create_empty_frame_metadata(config=camera_config,
                                                         frame_number=orchestrator.camera_frame_count[camera_id].value+1)
            print_in_wait = True
            orchestrator.camera_frame_count[camera_id].value += 1 # last camera to do this will break the others out of their wait loops
            while should_continue() and not orchestrator.should_grab_by_id(camera_id=camera_id):
                if print_in_wait:
                    print(f"{frame_tab}Camera {camera_id} waiting cameras ready:"
                          f" frame_counts_by_camera_id={[cam_id+':'+str(counter.value) for cam_id, counter in orchestrator.camera_frame_count.items()]}")
                    print_in_wait = False
                wait_1ms() if not ludacris_speed else None



            print(f"{frame_tab}Camera {camera_id} grabbing frame ")
            opencv_get_frame(cap=cv2_video_capture,
                             frame_metadata=frame_metadata,
                             camera_shared_memory=camera_shm,
                             )
            # Check if the camera config has changed
            if camera_config != ipc.get_config_by_id(camera_id=camera_id, with_lock=False):
                camera_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                           config=deepcopy(ipc.camera_configs[camera_id]),
                                                           initial=False)
                ipc.set_config_by_id(camera_id=camera_id,
                                     camera_config=camera_config, )
                logger.debug(f"Camera {camera_id} config updated to: {camera_config}")
            # print(f"{frame_tab}Camera {camera_id} frame grab completed")

    except Exception as e:
        logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
        raise
    finally:
        logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
        close_self_flag.value = True
        if cv2_video_capture:
            cv2_video_capture.release()
        camera_shm.close()

        logger.debug(f"Camera {camera_config.camera_index} process completed")
