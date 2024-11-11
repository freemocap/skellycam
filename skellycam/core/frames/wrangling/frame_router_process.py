import logging
import multiprocessing
from collections import deque
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.system.default_paths import get_default_recording_folder_path
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameRouterProcess:
    def __init__(self,
                 camera_group_dto: CameraGroupDTO,
                 multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO,
                 new_configs_queue: multiprocessing.Queue,
                 ):

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_group_dto,
                                                      multi_frame_escape_shm_dto,
                                                      new_configs_queue,
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
    def _run_process(camera_group_dto: CameraGroupDTO,
                     multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO,
                     new_configs_queue: multiprocessing.Queue,
                     ):

        logger.debug(f"FrameRouter  process started!")
        mf_payloads_to_process: deque[MultiFramePayload] = deque()
        recording_manager: Optional[RecordingManager] = None
        frame_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer = MultiFrameEscapeSharedMemoryRingBuffer.recreate(
            camera_group_dto=camera_group_dto,
            shm_dto=multi_frame_escape_shm_dto,
            read_only=False)

        camera_configs = camera_group_dto.camera_configs

        previous_mf_payload_pulled_from_shm: Optional[MultiFramePayload] = None
        previous_mf_payload_pulled_from_deque: Optional[MultiFramePayload] = None

        try:
            while not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                wait_1ms()

                # Check for new camera configs
                if new_configs_queue.qsize() > 0:
                    camera_configs = new_configs_queue.get()

                # Fully drain the ring shm buffer every time and put the frames into a deque in this Process' memory
                while frame_escape_ring_shm.new_multi_frame_available:
                    mf_payload: MultiFramePayload = frame_escape_ring_shm.get_multi_frame_payload(
                        camera_configs=camera_configs,
                        retrieve_type="next")
                    # print(f"ROUTER - pulled mf_payload #{mf_payload.multi_frame_number} from ring buffer (mf_payloads_to_process: {len(mf_payloads_to_process)})")
                    if previous_mf_payload_pulled_from_shm:
                        if not mf_payload.multi_frame_number == previous_mf_payload_pulled_from_shm.multi_frame_number + 1:
                            raise ValueError(
                                f"FrameRouter expected mf_payload #{previous_mf_payload_pulled_from_shm.multi_frame_number + 1}, but got #{mf_payload.multi_frame_number}")
                    previous_mf_payload_pulled_from_shm = mf_payload
                    mf_payloads_to_process.append(mf_payload)

                # If we're recording, create a VideoRecorderManager and load all available frames into it (but don't save them to disk yet)
                if camera_group_dto.ipc_flags.record_frames_flag.value:
                    while len(mf_payloads_to_process) > 0:
                        mf_payload = mf_payloads_to_process.popleft()
                        if previous_mf_payload_pulled_from_deque:
                            if not mf_payload.multi_frame_number == previous_mf_payload_pulled_from_deque.multi_frame_number + 1:
                                raise ValueError(
                                    f"FrameRouter expected mf_payload #{previous_mf_payload_pulled_from_deque.multi_frame_number + 1}, but got #{mf_payload.multi_frame_number}")
                        previous_mf_payload_pulled_from_deque = mf_payload
                        if not recording_manager:
                            recording_manager = RecordingManager.create(multi_frame_payload=mf_payload,
                                                                             camera_configs=camera_group_dto.camera_configs,
                                                                             mic_device_index=camera_group_dto.ipc_flags.mic_device_index.value if not camera_group_dto.ipc_flags.mic_device_index.value != -1 else None,
                                                                             recording_folder=get_default_recording_folder_path(
                                                                                     tag=""))
                            camera_group_dto.ipc_queue.put(recording_manager.recording_info)
                        recording_manager.add_multi_frame(mf_payload)
                else:
                    # If we're not recording and recording_manager exists, finish up the videos and close the recorder
                    if recording_manager:
                        logger.info('Recording complete, finishing and closing recorder...')
                        while len(mf_payloads_to_process) > 0:
                            print(
                                f"\t\tROUTER (POST-REC) - adding mf_payload #{mf_payloads_to_process[0].multi_frame_number} to recording_manager")
                            recording_manager.add_multi_frame(mf_payloads_to_process.popleft())
                        recording_manager.finish_and_close()

                        recording_manager = None

                    # If we're not recording, just clear the deque of frames
                    mf_payloads_to_process.clear()
                    # TODO - send mf_payload along to the processing pipeline, somehow (maybe via another pipe? or the SharedMemoryIndexedArray thing i made?)

                # If we're recording, save one frame from the recording_manager each loop (skips if no frames to save)
                if recording_manager:
                    recording_manager.save_one_frame()

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
            if not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                logger.warning("FrameRouter should only be closed after global kill flag is set")
                camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            if recording_manager:
                recording_manager.finish_and_close()
            logger.debug(f"FrameRouter process completed")
            frame_escape_ring_shm.close()
