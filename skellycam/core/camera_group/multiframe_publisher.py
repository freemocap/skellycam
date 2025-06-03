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
from skellycam.utilities.wait_functions import wait_1ms, wait_10ms

logger = logging.getLogger(__name__)


@dataclass
class MultiframePublisher:
    worker: multiprocessing.Process
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO):
        worker = multiprocessing.Process(target=cls._mf_publication_worker,
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
        logger.debug(f"Starting multi-frame publication process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self):
        self.worker.join()

    def close(self):
        logger.debug(f"Closing multi-frame publication process...")
        self.ipc.should_continue = False
        if self.is_alive():
            self.join()
        logger.debug(f"Multiframe publisher closed")

    @staticmethod
    def _mf_publication_worker(ipc: CameraGroupIPC,
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

        previous_mf: MultiFramePayload | None = None
        logger.debug(f"Multiframe Saver process started")
        try:
            while ipc.should_continue:
                wait_10ms()
                latest_mfs = camera_group_shm.publish_all_new_multiframes(previous_payload=previous_mf,
                                                                          overwrite=True)
                logger.loop(f"Published multiframe numbers: {[mf.multi_frame_number for mf in latest_mfs]}")

        except Exception as e:
            logger.error(f"Process error: {e}")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            pass
        finally:
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")
