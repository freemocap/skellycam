import enum
import logging
import multiprocessing
from dataclasses import dataclass

import cv2

from skellycam.core.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.apply_config import apply_camera_configuration
from skellycam.core.camera.opencv_camera_run_process import opencv_camera_run_process
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.orchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.shared_memory.single_slot_camera_shared_memory import \
    CameraSharedMemoryDTO
from skellycam.core.types import CameraIdString
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue

logger = logging.getLogger(__name__)


class CameraStrategies(enum.Enum):
    OPEN_CV = "OPEN_CV"


@dataclass
class CameraProcess:
    camera_id: CameraIdString
    process: multiprocessing.Process
    ipc: CameraGroupIPC
    close_self_flag: multiprocessing.Value

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               ipc: CameraGroupIPC,
               orchestrator: CameraGroupOrchestrator,
               camera_shm_dto: CameraSharedMemoryDTO,
               camera_strategy: CameraStrategies = CameraStrategies.OPEN_CV,
               ludacris_speed: bool=False):

        if camera_strategy == CameraStrategies.OPEN_CV:
            logger.info(f"Creating OpenCV camera process for camera {camera_id} ")
            camera_run_process = opencv_camera_run_process
        else:
            raise ValueError(f"Unsupported camera strategy: {camera_strategy}")
        close_self_flag = multiprocessing.Value("b", False)
        return cls(camera_id=camera_id,
                   ipc=ipc,
                   close_self_flag=close_self_flag,
                   process=multiprocessing.Process(target=camera_run_process,
                                                   name=f"Camera{ipc.camera_configs[camera_id].camera_index}-{camera_id}-Process",
                                                   daemon=True,
                                                   kwargs=dict(camera_id=camera_id,
                                                               ipc=ipc,
                                                               orchestrator=orchestrator,
                                                               camera_shm_dto=camera_shm_dto,
                                                               close_self_flag=close_self_flag,
                                                               ws_queue=get_websocket_log_queue(),
                                                               ludacris_speed=ludacris_speed
                                                               )
                                                   ),

                   )

    def start(self):
        self.process.start()

    def close(self):
        logger.info(f"Closing camera {self.camera_id}")
        self.close_self_flag.value = True
        self.process.join()
        logger.info(f"Camera {self.camera_id} closed!")

    def is_alive(self) -> bool:
        return self.process.is_alive()



