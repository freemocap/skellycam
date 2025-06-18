import enum
import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_camera_run_process import opencv_camera_worker_method
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.recorders.recording_manager import WorkerType
from skellycam.core.types.type_overloads import CameraIdString, WorkerStrategy, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


class CameraStrategies(enum.Enum):
    OPEN_CV = opencv_camera_worker_method




@dataclass
class CameraWorker:
    camera_id: CameraIdString
    worker: WorkerType
    ipc: CameraGroupIPC
    close_self_flag: multiprocessing.Value

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               ipc: CameraGroupIPC,
               config: CameraConfig,
               update_camera_settings_subscription: TopicSubscriptionQueue,
                shm_subscription: TopicSubscriptionQueue,
               camera_worker_strategy: WorkerStrategy,
               camera_strategy: CameraStrategies = CameraStrategies.OPEN_CV,
               ):


        close_self_flag = multiprocessing.Value("b", False)


        return cls(camera_id=camera_id,
                   ipc=ipc,
                   close_self_flag=close_self_flag,
                   worker=camera_worker_strategy.value(target=camera_strategy,
                                       name=f"Camera{config.camera_index}-{camera_id}-Process",
                                       daemon=True,
                                       kwargs=dict(camera_id=camera_id,
                                                   ipc=ipc,
                                                   config=config,
                                                   close_self_flag=close_self_flag,
                                                   update_camera_settings_subscription=update_camera_settings_subscription,
                                                   shm_subscription=shm_subscription,
                                                   camera_worker_strategy=camera_worker_strategy,
                                                   )
                                       )
                   ,
                   )

    def start(self):
        self.worker.start()

    def join(self):
        self.worker.join()

    def close(self):
        logger.info(f"Closing camera {self.camera_id}")
        self.close_self_flag.value = True
        self.worker.join()
        logger.info(f"Camera {self.camera_id} closed!")

    def is_alive(self) -> bool:
        return self.worker.is_alive()
