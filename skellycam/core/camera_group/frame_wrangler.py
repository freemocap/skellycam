import logging
import multiprocessing
from copy import deepcopy
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, CameraGroupSharedMemory
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class FrameWrangler:
    worker: multiprocessing.Process
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
                 ipc: CameraGroupIPC,
                 group_shm_dto: CameraGroupSharedMemoryDTO):
        worker = multiprocessing.Process(target=cls._run_process,
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
        logger.debug(f"Starting frame wrangler process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self):
        self.worker.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self.ipc.should_continue = False
        if self.is_alive():
            self.join()
        logger.debug(f"Frame wrangler closed")

    @staticmethod
    def _run_process(ipc: CameraGroupIPC,
                     group_shm_dto: CameraGroupSharedMemoryDTO,
                     ws_logs_queue: multiprocessing.Queue
                     ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ws_logs_queue)


        camera_group_shm: CameraGroupSharedMemory = CameraGroupSharedMemory.recreate_from_dto(
            ipc=ipc,
            shm_dto=group_shm_dto,
            read_only=False)

        recording_manager: RecordingManager | None = None
        audio_recorder: AudioRecorder | None = None
        previous_mf:MultiFramePayload|None = None
        logger.debug(f"FrameWrangler process started!")
        try:
            while ipc.should_continue:
                wait_1ms()
                if camera_group_shm.new_multi_frame_available:

                    latest_mfs = camera_group_shm.publish_all_new_multiframes(previous_payload=previous_mf, overwrite=True)
                    if len(latest_mfs) > 0 and isinstance(latest_mfs[-1], MultiFramePayload):
                        if previous_mf is None:
                            logger.debug(f"Pulled first multiframe(s) from camera group: {latest_mfs[-1].camera_ids}")
                        previous_mf = latest_mfs[-1]
                    logger.loop(f"Pulled multiframe numbers: {[mf.multi_frame_number for mf in latest_mfs]} from camera buffers")
                    # If we're recording, create a VideoRecorderManager and load all available frames into it (but don't save them to disk yet)
                    if recording_manager:
                        if ipc.record_frames_flag.value:
                            recording_manager.add_multi_frames(latest_mfs)
                        else:
                            recording_manager.finish_and_close()
                            recording_manager = None

                    else:
                        if ipc.record_frames_flag.value and not recording_manager and previous_mf:
                            recording_manager = RecordingManager.create(
                                recording_info=ipc.recording_info_queue.get(),
                                initial_multi_frame_payload= previous_mf,
                            )

                    if not ipc.recording_info_queue.empty() and previous_mf:
                        if recording_manager:
                            logger.error(f"Got new recording info while already recording! Finishing current recording before starting new one.")
                            recording_manager.finish_and_close()
                            raise RuntimeError(f"Got new recording info while already recording! Finishing current recording before starting new one.")
                        recording_manager = RecordingManager.create(
                            recording_info=ipc.recording_info_queue.get(),
                            initial_multi_frame_payload=previous_mf,
                        )

                    # if no new multi-frame is available and we're recording, opportunistically save frame to video. Otherwise, we keep mf's in the recording manager until there is time to process them (or on recording stop)
                    else:
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
            if recording_manager:
                recording_manager.finish_and_close()
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")
