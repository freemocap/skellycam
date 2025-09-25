import logging
import os
from dataclasses import dataclass

from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.types.type_overloads import WorkerStrategy, CameraIdString

logger = logging.getLogger(__name__)


@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    orchestrator: CameraOrchestrator
    camera_workers: dict[CameraIdString, CameraWorker]

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               camera_strategy: WorkerStrategy,
               camera_configs: CameraConfigs):

        logger.info(f"Starting camera manager process with {len(camera_configs)} cameras")

        camera_statuses: dict[CameraIdString, CameraStatus] = {camera_id: CameraStatus() for camera_id in
                                                               camera_configs.keys()}
        orchestrator = CameraOrchestrator.from_statuses(camera_statuses=camera_statuses)

        camera_workers = {camera_id: CameraWorker.create(
            camera_id=camera_id,
            ipc=ipc,
            orchestrator=orchestrator,
            config=camera_config,
            camera_worker_type=camera_strategy,
            update_camera_settings_subscription=ipc.pubsub.topics[
                TopicTypes.UPDATE_CAMERA_SETTINGS].get_subscription(),
            shm_subscription=ipc.pubsub.topics[
                TopicTypes.SHM_UPDATES].get_subscription(),
            recording_info_subscription=ipc.pubsub.topics[
                TopicTypes.RECORDING_INFO].get_subscription(),
        ) for camera_id, camera_config in camera_configs.items()}

        return cls(
            ipc=ipc,
            camera_workers=camera_workers,
            orchestrator=orchestrator
        )



    def start(self):
        logger.info("Starting camera processes...")
        for worker in self.camera_workers.values():
            worker.start()

    def pause(self, await_paused: bool):
        self.orchestrator.pause(await_paused=await_paused)

    def unpause(self, await_unpaused: bool):
        self.orchestrator.unpause(await_unpaused=await_unpaused)

    def close(self):
        logger.info("Closing camera manager and all camera processes...")
        self.ipc.should_continue = False
        for worker in self.camera_workers.values():
            if worker.is_alive():
                worker.worker.join(timeout=2.0)
                if worker.is_alive():
                    logger.warning(f"Camera worker {worker.camera_id} did not shutdown gracefully, terminating...")
                    worker.worker.terminate()
                    worker.worker.join(timeout=2.0)
                    if worker.is_alive():
                        pid = worker.worker.pid
                        os.kill(pid, 9)  # Force kill
                        logger.error(f"Camera worker {worker.camera_id} (PID: {pid}) had to be force killed.")
                else:
                    logger.info(f"Camera worker {worker.camera_id} terminated successfully.")
            else:
                logger.info(f"Camera worker {worker.camera_id} was not alive.")
        self.camera_workers.clear()
        logger.success("Camera manager closed all camera processes successfully.")
