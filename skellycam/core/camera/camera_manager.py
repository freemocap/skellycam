import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.types.type_overloads import WorkerStrategy, WorkerType, TopicSubscriptionQueue, CameraIdString
from skellycam.utilities.wait_functions import wait_1s

logger = logging.getLogger(__name__)


@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    worker: WorkerType

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               camera_configs: CameraConfigs,
               camera_strategy: WorkerStrategy):
        if camera_strategy == WorkerStrategy.THREAD:
            camera_manager_strategy: WorkerStrategy = WorkerStrategy.PROCESS
        else:
            camera_manager_strategy: WorkerStrategy = WorkerStrategy.THREAD

        config_subscription_by_camera = {
            camera_id: ipc.pubsub.topics[TopicTypes.UPDATE_CAMERA_SETTINGS].get_subscription() for camera_id in
            camera_configs.keys()}
        shm_subscription_by_camera = {camera_id: ipc.pubsub.topics[TopicTypes.SHM_UPDATES].get_subscription() for
                                      camera_id in camera_configs.keys()}
        recording_info_subscription_by_camera = {
            camera_id: ipc.pubsub.topics[TopicTypes.RECORDING_INFO].get_subscription() for camera_id in
            camera_configs.keys()}
        worker = camera_manager_strategy.value(
            target=cls._camera_manager_worker,
            name=f"{cls.__name__}-Worker",
            daemon=True,
            kwargs=dict(
                ipc=ipc,
                camera_configs=camera_configs,
                camera_strategy=camera_strategy,
                config_subscription_by_camera=config_subscription_by_camera,
                recording_info_subscription_by_camera=recording_info_subscription_by_camera,
                shm_subscription_by_camera=shm_subscription_by_camera,
            )
        )

        return cls(ipc=ipc,
                   worker=worker)

    @staticmethod
    def _camera_manager_worker(ipc: CameraGroupIPC,
                               camera_configs: CameraConfigs,
                               camera_strategy: WorkerStrategy,
                               config_subscription_by_camera: dict[CameraIdString, TopicSubscriptionQueue],
                               shm_subscription_by_camera: dict[CameraIdString, TopicSubscriptionQueue],
                               recording_info_subscription_by_camera: dict[CameraIdString, TopicSubscriptionQueue]
                               ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
        logger.info(f"Starting camera manager process with {len(camera_configs)} cameras")

        camera_workers: dict[CameraIdString, CameraWorker] = {}
        for camera_id, camera_config in camera_configs.items():
            camera_workers[camera_id] = CameraWorker.create(
                camera_id=camera_id,
                ipc=ipc,
                config=camera_config,
                camera_worker_strategy=camera_strategy,
                update_camera_settings_subscription=config_subscription_by_camera[camera_id],
                shm_subscription=shm_subscription_by_camera[camera_id],
                recording_info_subscription=recording_info_subscription_by_camera[camera_id],
            )

        for worker in camera_workers.values():
            worker.start()

        while ipc.should_continue:
            wait_1s()
        logger.debug("Awaiting camera processes to finish...")
        for camera_id, worker in camera_workers.items():
            worker.join()
            logger.debug(f"Camera worker {camera_id} has finished.")
        logger.info("Camera manager worker is shut down")

    def close(self):
        if self.worker and self.worker.is_alive():
            logger.debug("Closing camera manager worker...")
            self.ipc.should_continue = False
            self.worker.join()
        logger.success("Camera manager worker closed successfully.")

    @property
    def any_alive(self) -> bool:
        if not self.worker or not self.worker.is_alive():
            return False
        return True

    @property
    def all_ready(self) -> bool:
        return self.ipc.camera_orchestrator.all_cameras_ready

    @property
    def all_alive(self) -> bool:
        if not self.worker or not self.worker.is_alive():
            return False
        return True

    @property
    def cameras_connected(self) -> bool:
        return self.ipc.camera_orchestrator.all_cameras_ready

    def start(self):
        if not self.worker:
            raise ValueError("Camera manager worker not initialized!")

        logger.info("Starting camera manager process...")
        self.worker.start()

    def pause(self, await_paused: bool):
        logger.debug(f"Pausing cameras in camera manager...")
        self.ipc.camera_orchestrator.pause(await_paused=await_paused)

    def unpause(self, await_unpaused: bool):
        logger.debug(f"Unpausing cameras in camera manager...")
        self.ipc.camera_orchestrator.unpause(await_unpaused=await_unpaused)
