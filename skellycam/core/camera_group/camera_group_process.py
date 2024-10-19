import logging
from multiprocessing import Process

from skellycam.core.camera_group.camera.camera_manager import CameraManager
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)


class CameraGroupProcess:
    def __init__(
            self,
            dto: CameraGroupDTO,
    ):
        self._dto = dto
        self._process = Process(
            name=CameraGroupProcess.__name__,
            target=CameraGroupProcess._run_process,
            args=(dto,)
        )

    @property
    def process(self):
        return self._process

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self):
        logger.debug("Starting `CameraGroupProcess`...")
        self._process.start()

    def close(self):
        logger.debug("Closing `CameraGroupProcess`...")
        if not self._dto.ipc_flags.kill_camera_group_flag.value == True:
            raise ValueError("CameraGroupProcess was closed before the kill flag was set.")
        self._process.join()
        logger.debug("CameraGroupProcess closed.")

    @staticmethod
    def _run_process(dto: CameraGroupDTO):
        logger.debug(f"CameraGroupProcess started")

        frame_wrangler = FrameWrangler.create(dto)
        camera_manager = CameraManager.create(dto)

        try:
            frame_wrangler.start()
            camera_manager.start()

        except Exception as e:
            logger.error(f"CameraGroupProcess error: {e}")
            logger.exception(e)
            raise
        finally:
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            logger.debug(f"CameraGroupProcess completed")
