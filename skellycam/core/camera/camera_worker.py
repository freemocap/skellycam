import logging
from dataclasses import dataclass

from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_camera_worker_method import opencv_camera_worker_method
from skellycam.core.camera_group.camera_group_helpers.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_group_helpers.camera_orchestrator import CameraOrchestrator
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


class CameraState(BaseModel):
    """Serializable representation of a camera process state."""
    pid: int
    name: str
    alive: bool
    status: dict
    error: str | None = None


@dataclass
class CameraWorker:
    camera_id: CameraIdString
    worker: ManagedWorker
    ipc: CameraGroupIPC
    orchestrator: CameraOrchestrator

    @classmethod
    def create(
        cls,
        *,
        camera_id: CameraIdString,
        ipc: CameraGroupIPC,
        worker_registry: WorkerRegistry,
        config: CameraConfig,
        orchestrator: CameraOrchestrator,
        update_camera_settings_subscription: TopicSubscriptionQueue,
        shm_subscription: TopicSubscriptionQueue,
        recording_info_subscription: TopicSubscriptionQueue,
    ) -> "CameraWorker":
        worker = worker_registry.create_worker(
            target=opencv_camera_worker_method,
            name=f"Camera{config.camera_index}-{camera_id}-Worker",
            log_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication,
            kwargs=dict(
                camera_id=camera_id,
                ipc=ipc,
                config=config,
                orchestrator=orchestrator,
                update_camera_settings_subscription=update_camera_settings_subscription,
                shm_subscription=shm_subscription,
                recording_info_subscription=recording_info_subscription,
            ),
        )
        return cls(
            camera_id=camera_id,
            ipc=ipc,
            orchestrator=orchestrator,
            worker=worker,
        )

    def start(self) -> None:
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self.worker.join(timeout=timeout)

    def to_state(self) -> CameraState:
        return CameraState(
            pid=self.worker.pid or -1,
            name=self.worker.name,
            alive=self.worker.is_alive(),
            status=self.orchestrator.camera_statuses[self.camera_id].serialize(),
        )
