import logging
import multiprocessing
from collections import deque
from pathlib import Path

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO
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
        configure_logging(LOG_LEVEL, ws_queue=camera_group_dto.ipc.ws_logs_queue)
        logger.debug(f"FrameSaver process started!")


        mf_payloads_to_process: deque[MultiFramePayload] = deque()
        recording_manager: RecordingManager|None = None
        frame_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer = MultiFrameEscapeSharedMemoryRingBuffer.recreate(
            camera_group_dto=camera_group_dto,
            shm_dto=multi_frame_escape_shm_dto,
            read_only=False)

        camera_configs = camera_group_dto.camera_configs

        previous_mf_payload_pulled_from_shm: MultiFramePayload|None = None
        previous_mf_payload_pulled_from_deque: MultiFramePayload|None = None
        recording_info: RecordingInfo|None = None
        audio_recorder: AudioRecorder|None = None
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
                                f"FrameSaver expected mf_payload #{previous_mf_payload_pulled_from_shm.multi_frame_number + 1}, but got #{mf_payload.multi_frame_number}")
                    previous_mf_payload_pulled_from_shm = mf_payload
                    mf_payloads_to_process.append(mf_payload)

                    # If we're recording, create a VideoRecorderManager and load all available frames into it (but don't save them to disk yet)
                    if not camera_group_dto.ipc.start_recording_queue.empty():
                        payload =  camera_group_dto.ipc.start_recording_queue.get()
                        if isinstance(payload, RecordingInfo):
                            recording_info: RecordingInfo = payload
                            logger.info(f"Starting recording with info: {recording_info.model_dump_json(indent=2)}")
                            camera_group_dto.ipc.record_frames_flag.value = True
                        elif payload is None:
                            logger.info(f"Stopping recording with info: {recording_info.model_dump_json(indent=2)}")
                            camera_group_dto.ipc.record_frames_flag.value = False


                    while len(mf_payloads_to_process) > 0:
                        if not camera_group_dto.ipc.global_should_continue:
                            logger.critical(
                                "FrameSaverProcess received kill signal before recording was complete!! Recording may be incomplete or corrupt!")
                            break
                        mf_payload = mf_payloads_to_process.popleft()
                        if previous_mf_payload_pulled_from_deque:
                            if not mf_payload.multi_frame_number == previous_mf_payload_pulled_from_deque.multi_frame_number + 1:
                                raise ValueError(
                                    f"FrameSaver expected mf_payload #{previous_mf_payload_pulled_from_deque.multi_frame_number + 1}, but got #{mf_payload.multi_frame_number}")
                        previous_mf_payload_pulled_from_deque = mf_payload
                        if camera_group_dto.ipc.record_frames_flag.value:
                            if not recording_manager:
                                recording_manager = RecordingManager.create(multi_frame_payload=mf_payload,
                                                                            camera_configs=camera_group_dto.camera_configs,
                                                                            recording_folder = recording_info.full_recording_path,
                                                                            )
                                if recording_info.mic_device_index != -1:
                                    audio_file_path = str(Path(
                                        recording_manager.videos_folder) / f"{recording_manager.recording_name}_audio.wav")
                                    audio_recorder = AudioRecorder(audio_file_path=audio_file_path,
                                                                   mic_device_index=camera_group_dto.ipc.mic_device_index.value)
                                    audio_recorder.start()
                            recording_manager.add_multi_frame(mf_payload)

                    # If we're not recording and recording_manager exists, finish up the videos and close the recorder
                    if recording_manager and not camera_group_dto.ipc.record_frames_flag.value:
                        logger.info('Recording complete, finishing and closing recorder...')
                        previous_mf_payload_pulled_from_deque = None
                        while len(mf_payloads_to_process) > 0:
                            recording_manager.add_multi_frame(mf_payloads_to_process.popleft())
                        recording_manager.finish_and_close()
                        recording_manager = None
                        if audio_recorder:
                            audio_recorder.stop()
                            audio_recorder = None

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
            if camera_group_dto.should_continue:
                logger.error("FrameSaver shut down for unknown reason! `camera_group_dto.should_continue` is True")
                camera_group_dto.ipc.kill_camera_group_flag.value = True
            if recording_manager:
                recording_manager.finish_and_close()
            logger.debug(f"FrameSaver process completed")
            frame_escape_ring_shm.close()
