import logging
import threading

from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import MultiFrameEscapeSharedMemoryRingBufferDTO
from skellycam.core.playback.video_group_dto import VideoGroupDTO
from skellycam.core.playback.video_playback_handler import video_playback_handler

logger = logging.getLogger(__name__)


class VideoGroupThread:
    def __init__(
            self,
            video_group_dto: VideoGroupDTO,
            multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO,
    ):
        self.dto = video_group_dto
        self._thread = threading.Thread(
            name=VideoGroupThread.__name__,
            target=VideoGroupThread._run_thread,
            kwargs=dict(video_group_dto=video_group_dto,
                  multi_frame_escape_shm_dto=multi_frame_escape_shm_dto,
                  )
        )

    @property
    def thread(self):
        return self._thread

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        logger.debug("Starting `VideoGroupThread`...")
        self._thread.start()

    def close(self):
        logger.debug("Closing `VideoGroupThread`...")
        if not self.dto.ipc_flags.kill_camera_group_flag.value == True:
            logger.warning("VideoGroupThread was closed before the kill flag was set.")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        self._thread.join()
        logger.debug("VideoGroupThread closed.")

    @staticmethod
    def _run_thread(video_group_dto: VideoGroupDTO,
                    multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO,
                ):
        logger.debug(f"VideoGroupThread started")

        try:
            video_playback_handler(video_group_dto=video_group_dto, multi_frame_escape_shm_dto=multi_frame_escape_shm_dto)

        except Exception as e:
            logger.error(f"VideoGroupThread error: {e}")
            logger.exception(e)
            raise
        finally:
            # cleanup code here
            logger.debug(f"VideoGroupThread completed")
