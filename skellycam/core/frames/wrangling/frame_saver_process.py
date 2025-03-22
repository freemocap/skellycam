import logging
import multiprocessing
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.system.default_paths import get_default_recording_folder_path
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameSaverProcess:
    def __init__(self,
                 camera_group_dto: CameraGroupDTO,
                 multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO,
                 new_configs_queue: multiprocessing.Queue,
                 ):

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                kwargs=dict(camera_group_dto=camera_group_dto,
                                                            multi_frame_escape_shm_dto=multi_frame_escape_shm_dto,
                                                            new_configs_queue=new_configs_queue,
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
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=camera_group_dto.logs_queue)
        logger.debug(f"FrameRouter process started!")

        def heartbeat_thread_function():
            heart_beat_counter = 0
            while camera_group_dto.should_continue:
                heart_beat_counter += 1
                if heart_beat_counter % 10 == 0:
                    logger.trace(f"FrameSaverProcess heartbeat says 'beep'")
                time.sleep(1)

        heartbeat_thread = threading.Thread(target=heartbeat_thread_function,
                                            daemon=True,
                                            name=f"FrameSaverProcess_heartbeat")
        # heartbeat_thread.start()

        mf_payloads_to_process: deque[MultiFramePayload] = deque()
        recording_manager: Optional[RecordingManager] = None
        frame_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer = MultiFrameEscapeSharedMemoryRingBuffer.recreate(
            camera_group_dto=camera_group_dto,
            shm_dto=multi_frame_escape_shm_dto,
            read_only=False)

        camera_configs = camera_group_dto.camera_configs

        previous_mf_payload_pulled_from_shm: Optional[MultiFramePayload] = None
        previous_mf_payload_pulled_from_deque: Optional[MultiFramePayload] = None

        audio_recorder: Optional[AudioRecorder] = None
        try:
            while camera_group_dto.should_continue:
                wait_1ms()

                # Check for new camera configs
                if not new_configs_queue.empty():
                    camera_configs = new_configs_queue.get()

                # Fully drain the ring shm buffer every time and put the frames into a deque in this Process' memory
                while frame_escape_ring_shm.new_multi_frame_available and camera_group_dto.should_continue:
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
                        if not camera_group_dto.ipc_flags.global_should_continue:
                            logger.critical(
                                "FrameSaverProcess received kill signal before recording was complete!! Recording may be incomplete or corrupt!")
                            break
                        mf_payload = mf_payloads_to_process.popleft()
                        if previous_mf_payload_pulled_from_deque:
                            if not mf_payload.multi_frame_number == previous_mf_payload_pulled_from_deque.multi_frame_number + 1:
                                raise ValueError(
                                    f"FrameRouter expected mf_payload #{previous_mf_payload_pulled_from_deque.multi_frame_number + 1}, but got #{mf_payload.multi_frame_number}")
                        previous_mf_payload_pulled_from_deque = mf_payload
                        if not recording_manager:
                            recording_manager = RecordingManager.create(multi_frame_payload=mf_payload,
                                                                        camera_configs=camera_group_dto.camera_configs,
                                                                        recording_folder=camera_group_dto.ipc_flags.recording_name.value.decode(
                                                                                "utf-8")
                                                                        )
                            if camera_group_dto.ipc_flags.mic_device_index.value != -1:
                                audio_file_path = str(Path(
                                    recording_manager.videos_folder) / f"{recording_manager.recording_name}_audio.wav")
                                audio_recorder = AudioRecorder(audio_file_path=audio_file_path,
                                                               mic_device_index=camera_group_dto.ipc_flags.mic_device_index.value)
                                audio_recorder.start()
                            camera_group_dto.ipc_queue.put(recording_manager.recording_info)
                        recording_manager.add_multi_frame(mf_payload)
                else:
                    # If we're not recording and recording_manager exists, finish up the videos and close the recorder
                    if recording_manager:
                        logger.info('Recording complete, finishing and closing recorder...')
                        previous_mf_payload_pulled_from_deque = None
                        while len(mf_payloads_to_process) > 0:
                            recording_manager.add_multi_frame(mf_payloads_to_process.popleft())
                        recording_manager.finish_and_close()

                        recording_manager = None
                        if audio_recorder:
                            audio_recorder.stop()
                            audio_recorder = None

                    # If we're not recording, just clear the deque of frames
                    mf_payloads_to_process.clear()

                # If we're recording, save one frame from the recording_manager each loop (skips if no frames to save)
                if recording_manager:
                    recording_manager.save_one_frame()

        except Exception as e:
            logger.error(f"Frame Saver process error: {e}")
            logger.exception(e)
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame Saver process error: {e} - Broken pipe error, problem in FrameListenerProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            pass
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if camera_group_dto.should_continue:
                logger.error("FrameSaver shut down for unknown reason! `camera_group_dto.should_continue` is True")
                camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            if recording_manager:
                recording_manager.finish_and_close()
            logger.debug(f"FrameRouter process completed")
            frame_escape_ring_shm.close()
