import logging
import multiprocessing
from collections import deque
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_ring_buffer import \
    SharedMemoryRingBufferDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    SingleSlotCameraGroupSharedMemory, SingleSlotCameraGroupSharedMemoryDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.videos.video_recorder_manager import VideoRecorderManager
from skellycam.system.default_paths import get_default_recording_folder_path
from skellycam.utilities.wait_functions import wait_1ms, wait_100ms

logger = logging.getLogger(__name__)


class FrameRouterProcess:
    def __init__(self,
                 camera_group_dto: CameraGroupDTO,
                 new_configs_queue: multiprocessing.Queue,
                 frame_escape_ring_shm_dto: SharedMemoryRingBufferDTO, ):

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_group_dto,
                                                      new_configs_queue,
                                                      frame_escape_ring_shm_dto,
                                                      )
                                                )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()

    @staticmethod
    def _run_process(dto: CameraGroupDTO,
                     new_configs_queue: multiprocessing.Queue,
                     frame_escape_ring_shm_dto: SingleSlotCameraGroupSharedMemoryDTO,
                     ):
        """
        This process is not coupled to the frame loop, and the `escape pipe` is elastic, so blocking is not as big a sin here.
        MultiFrame chunks will be sent through the `frame_escape_pipe` and will be gathered, reconstructed into a framepayload, and handled here.
        """
        logger.debug(f"FrameRouter  process started!")
        mf_payloads_to_process: deque[MultiFramePayload] = deque()
        video_recorder_manager: Optional[VideoRecorderManager] = None
        frame_escape_ring_shm = SingleSlotCameraGroupSharedMemory.recreate(camera_group_dto=dto,
                                                                           shm_dto=frame_escape_ring_shm_dto,
                                                                           read_only=False)
        camera_configs = dto.camera_configs
        mf_payload: Optional[MultiFramePayload] = None
        try:
            while not dto.ipc_flags.kill_camera_group_flag.value and not dto.ipc_flags.global_kill_flag.value:
                if new_configs_queue.qsize() > 0:
                    camera_configs = new_configs_queue.get()
                wait_100ms()
                # mf_payload: Optional[MultiFramePayload] = frame_escape_ring_shm.get_multi_frame_payload(previous_payload=mf_payload,
                #                                                                                         camera_configs=camera_configs)
                #
                # # if frame_escape_ring_shm.new
                # #     shm_ring_buffer_dto: SharedMemoryRingBufferDTO = frame_escape_pipe.recv()
                # #     if shm_ring_buffer:
                # #         shm_ring_buffer.close()
                # #     shm_ring_buffer = SharedMemoryRingBuffer.recreate(shm_ring_buffer_dto)
                # #
                # # if shm_ring_buffer and shm_ring_buffer.new_data_available:
                # #     bytes_payload = shm_ring_buffer.get_data()
                # #     mf_payload = MultiFramePayload.from_bytes_buffer(bytes_payload)
                # #     mf_payloads_to_process.append(mf_payload)
                # # else:
                # #     if video_recorder_manager and video_recorder_manager.frames_to_save and not frame_escape_pipe.poll():  # prioritize other work before saving a frame
                # #         video_recorder_manager.save_one_frame()  # passes if empty
                #
                # # Handle multi-frame payloads
                # if len(mf_payloads_to_process) > 0:
                #     mf_payload = mf_payloads_to_process.popleft()
                #     if dto.ipc_flags.record_frames_flag.value:
                #         if not video_recorder_manager:
                #
                #             video_recorder_manager = VideoRecorderManager.create(multi_frame_payload=mf_payload,
                #                                                                  camera_configs=dto.camera_configs,
                #                                                                  recording_folder=get_default_recording_folder_path(
                #                                                                      tag=""))
                #             dto.ipc_queue.put(video_recorder_manager.recording_info)
                #         video_recorder_manager.add_multi_frame(mf_payload)
                #     else:
                #         if video_recorder_manager:
                #             logger.info('Recording complete, finishing and closing recorder...')
                #             while len(mf_payloads_to_process) > 0:
                #                 video_recorder_manager.add_multi_frame(mf_payloads_to_process.popleft())
                #             video_recorder_manager.finish_and_close()  # Note, this will block this process until all frames are written
                #             video_recorder_manager = None
                #     # TODO - send mf_payload along to the processing pipeline, somehow (maybe via another pipe? or the SharedMemoryIndexedArray thing i made?)


        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
            logger.exception(e)
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame exporter process error: {e} - Broken pipe error, problem in FrameListenerProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            logger.info(f"Frame exporter process received KeyboardInterrupt, shutting down gracefully...")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if not dto.ipc_flags.kill_camera_group_flag.value and not dto.ipc_flags.global_kill_flag.value:
                logger.warning("FrameRouter should only be closed after global kill flag is set")

            if video_recorder_manager:
                video_recorder_manager.finish_and_close()
            logger.debug(f"FrameRouter process completed")
            # if shm_ring_buffer:
            #     shm_ring_buffer.close()
