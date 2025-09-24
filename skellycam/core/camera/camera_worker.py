import enum
import logging
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_camera_worker_method import opencv_camera_worker_method
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue, WorkerType

logger = logging.getLogger(__name__)


class CameraStrategies(enum.Enum):
    OPEN_CV = opencv_camera_worker_method


@dataclass
class CameraWorker:
    camera_id: CameraIdString
    worker: WorkerType
    ipc: CameraGroupIPC
    orchestrator: CameraOrchestrator
    status: CameraStatus

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               ipc: CameraGroupIPC,
               config: CameraConfig,
               orchestrator: CameraOrchestrator,
               status: CameraStatus,
               update_camera_settings_subscription: TopicSubscriptionQueue,
               shm_subscription: TopicSubscriptionQueue,
               recording_info_subscription: TopicSubscriptionQueue,
               camera_worker_type: WorkerType,
               camera_strategy: CameraStrategies = CameraStrategies.OPEN_CV,
               ):
        return cls(camera_id=camera_id,
                   ipc=ipc,
                   status=status,
                   orchestrator=orchestrator,
                   worker=camera_worker_type.value(target=camera_strategy,
                                                   name=f"Camera{config.camera_index}-{camera_id}-Process",
                                                   daemon=True,
                                                   kwargs=dict(camera_id=camera_id,
                                                               ipc=ipc,
                                                               config=config,
                                                               status=status,
                                                               orchestrator=orchestrator,
                                                               update_camera_settings_subscription=update_camera_settings_subscription,
                                                               shm_subscription=shm_subscription,
                                                               recording_info_subscription=recording_info_subscription,
                                                               camera_worker_strategy=camera_worker_type,
                                                               )
                                                   )
                   ,
                   )

    def start(self):
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self, timeout: float | None = None):
        self.worker.join(timeout=timeout)

    def close(self):
        pass
