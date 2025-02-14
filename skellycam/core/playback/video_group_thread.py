import logging
import multiprocessing
import threading
from multiprocessing import Process

from skellycam.core.camera_group.camera.camera_manager import CameraManager
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler
from skellycam.core.playback.video_group_dto import VideoGroupDTO

logger = logging.getLogger(__name__)


class VideoGroupThread:
    def __init__(
            self,
            video_group_dto: VideoGroupDTO,
            shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
    ):
        self.dto = video_group_dto
        self._thread = threading.Thread(
            name=VideoGroupThread.__name__,
            target=VideoGroupThread._run_thread,
            kwargs=dict(camera_group_dto=video_group_dto,
                  shmorc_dto=shmorc_dto,
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
    def _run_thread(camera_group_dto: CameraGroupDTO,
                    shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,):
        logger.debug(f"VideoGroupThread started")


        try:
            pass

        except Exception as e:
            logger.error(f"VideoGroupThread error: {e}")
            logger.exception(e)
            raise
        finally:
            # cleanup code here
            logger.debug(f"VideoGroupThread completed")
