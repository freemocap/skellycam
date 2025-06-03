import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.types import RecordingManagerIdString
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class VideoManager:
    worker: multiprocessing.Process
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO):
        worker = multiprocessing.Process(target=cls._mf_subscription_video_worker,
                                         name=cls.__class__.__name__,
                                         kwargs=dict(ipc=ipc,
                                                     group_shm_dto=group_shm_dto,
                                                     ws_logs_queue=get_websocket_log_queue()
                                                     )
                                         )
        return cls(worker=worker,
                   ipc=ipc,
                   )

    def start(self):
        logger.debug(f"Starting video worker process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self):
        self.worker.join()

    def close(self):
        logger.debug(f"Closing video worker process...")
        self.ipc.should_continue = False
        if self.is_alive():
            self.join()
        logger.debug(f"Video worker closed")

    @staticmethod
    def _mf_subscription_video_worker(ipc: CameraGroupIPC,
                                      group_shm_dto: CameraGroupSharedMemoryDTO,
                                      ws_logs_queue: multiprocessing.Queue
                                      ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ws_logs_queue)

        camera_group_shm: CameraGroupSharedMemoryManager = CameraGroupSharedMemoryManager.recreate_from_dto(
            ipc=ipc,
            shm_dto=group_shm_dto,
            read_only=False)

        recording_managers: dict[RecordingManagerIdString, RecordingManager] | None = {}
        active_recording_manager_id: RecordingManagerIdString | None = None
        closing_recording_manager_id: RecordingManagerIdString | None = None
        audio_recorder: AudioRecorder | None = None
        previous_mf: MultiFramePayload | None = None
        logger.debug(f"FrameWrangler process started!")
        try:
            while ipc.should_continue:
                wait_1ms()

                new_mfs = camera_group_shm.get_all_new_multiframes()
                if len(new_mfs) > 0 and isinstance(new_mfs[-1], MultiFramePayload):
                    if previous_mf is None:
                        logger.debug(f"Pulled first multiframe(s) from camera group: {new_mfs[-1].camera_ids}")
                    previous_mf = new_mfs[-1]

                    # If we're recording, create a VideoRecorderManager and load all available frames into it (but don't save them to disk yet)
                    if active_recording_manager_id:
                        if ipc.record_frames_flag.value:
                            recording_managers[active_recording_manager_id].add_multi_frames(new_mfs)
                        else:
                            # if `recording_manager` exists but we're not recording, we finish and close it
                            closing_recording_manager_id = active_recording_manager_id
                            active_recording_manager_id = None
                else:
                    # If no new multiframe, do other tasks
                    if not ipc.recording_info_queue.empty() and previous_mf:
                        if active_recording_manager_id:
                            logger.warning(
                                f"Got new recording info while already recording! Finishing current recording before starting new one.")
                            closing_recording_manager_id = active_recording_manager_id

                        rec = RecordingManager.create(
                            recording_info=ipc.recording_info_queue.get(),
                            initial_multi_frame_payload=previous_mf,
                        )
                        recording_managers[rec.id] = rec
                        active_recording_manager_id = rec.id
                    else:
                        # opportunity to save one frame if we're recording
                        if active_recording_manager_id:
                            recording_managers[active_recording_manager_id].save_one_frame()

                if closing_recording_manager_id is not None and active_recording_manager_id is None and not ipc.record_frames_flag.value:
                    # Prioritize finishing the closing recording manager if we are not actively recording by saving one frame per loop iteration
                    if not recording_managers[closing_recording_manager_id].try_save_one_frame():
                        logger.info(
                            f"Finishing and closing videos for recording {recording_managers[closing_recording_manager_id].recording_info.recording_name}...")
                        recording_managers[closing_recording_manager_id].finish_and_close()
                        del recording_managers[closing_recording_manager_id]
                        closing_recording_manager_id = None

                    if previous_mf.multi_frame_number % 100 == 0:
                        logger.info(
                            f"Saving remaining frames to videos for recording {recording_managers[closing_recording_manager_id].recording_info.recording_name} (frames to save: {recording_managers[closing_recording_manager_id].frame_counts_to_save})...")


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
            if active_recording_manager_id:
                if recording_managers[active_recording_manager_id]:
                    recording_managers[active_recording_manager_id].finish_and_close()
            if closing_recording_manager_id:
                if recording_managers[closing_recording_manager_id]:
                    recording_managers[closing_recording_manager_id].finish_and_close()
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")
