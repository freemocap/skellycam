import logging
import multiprocessing
import threading

from skellycam.core.camera_group.camera.camera_manager import CameraManager
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)


class CameraGroupThread:
    def __init__(
            self,
            camera_group_dto: CameraGroupDTO,
            shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
            frame_router_config_queue: multiprocessing.Queue,
            frame_listener_config_queue: multiprocessing.Queue
    ):
        self.dto = camera_group_dto
        self._thread = threading.Thread(
            name=CameraGroupThread.__name__,
            target=CameraGroupThread._run_thread,
            kwargs=dict(camera_group_dto=camera_group_dto,
                  shmorc_dto=shmorc_dto,
                  frame_router_config_queue=frame_router_config_queue,
                  frame_listener_config_queue=frame_listener_config_queue
                  )
        )

    @property
    def thread(self):
        return self._thread

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        logger.debug("Starting `CameraGroupThread`...")
        self._thread.start()

    def close(self):
        logger.debug("Closing `CameraGroupThread`...")
        if not self.dto.ipc_flags.kill_camera_group_flag.value == True:
            logger.warning("CameraGroupThread was closed before the kill flag was set.")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        self._thread.join()
        logger.debug("CameraGroupThread closed.")

    @staticmethod
    def _run_thread(camera_group_dto: CameraGroupDTO,
                    shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                    frame_router_config_queue: multiprocessing.Queue,
                    frame_listener_config_queue: multiprocessing.Queue):
        logger.debug(f"CameraGroupThread started")

        frame_wrangler = FrameWrangler.create(camera_group_dto=camera_group_dto,
                                              shmorc_dto=shmorc_dto,
                                              frame_router_config_queue=frame_router_config_queue,
                                              frame_listener_config_queue=frame_listener_config_queue)

        camera_manager = CameraManager.create(camera_group_dto=camera_group_dto,
                                              shmorc_dto=shmorc_dto)

        try:
            frame_wrangler.start()
            camera_manager.start()

        except Exception as e:
            logger.error(f"CameraGroupThread error: {e}")
            logger.exception(e)
            raise
        finally:
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            logger.debug(f"CameraGroupThread completed")
