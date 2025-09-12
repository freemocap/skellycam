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
    ready_to_shutdown: multiprocessing.Value

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               camera_configs: CameraConfigs,
               camera_strategy: WorkerStrategy):
        # camera_strategy = WorkerStrategy.PROCESS
        # logger.debug(f"Creating Camera Manager with camera strategy: {camera_strategy}") 
        # if camera_strategy == WorkerStrategy.THREAD:
        #     camera_manager_strategy: WorkerStrategy = WorkerStrategy.PROCESS
        # else:
        #     camera_manager_strategy: WorkerStrategy = WorkerStrategy.THREAD
        camera_strategy = WorkerStrategy.THREAD
        camera_manager_strategy: WorkerStrategy = WorkerStrategy.THREAD
        logger.debug(f"Using camera manager strategy: {camera_manager_strategy.value}")
        ready_to_shutdown = multiprocessing.Value("b", False)
        config_subscription_by_camera = {
            camera_id: ipc.pubsub.topics[TopicTypes.UPDATE_CAMERA_SETTINGS].get_subscription() for camera_id in
            camera_configs.keys()}
        shm_subscription_by_camera = {camera_id: ipc.pubsub.topics[TopicTypes.SHM_UPDATES].get_subscription() for
                                      camera_id in camera_configs.keys()}
        recording_info_subscription_by_camera = {
            camera_id: ipc.pubsub.topics[TopicTypes.RECORDING_INFO].get_subscription() for camera_id in
            camera_configs.keys()}
        worker = camera_manager_strategy.value(  # Where thread/process is chosen
            target=cls._camera_manager_worker,  # could try calling this directly, make sure there aren't other threading instances
            name=f"{cls.__name__}-Worker",
            daemon=True,
            kwargs=dict(
                ipc=ipc,
                camera_configs=camera_configs,
                camera_strategy=camera_strategy,
                config_subscription_by_camera=config_subscription_by_camera,
                recording_info_subscription_by_camera=recording_info_subscription_by_camera,
                shm_subscription_by_camera=shm_subscription_by_camera,
                ready_to_shutdown=ready_to_shutdown
            )
        )
        logger.debug(f"Created camera manager worker {camera_manager_strategy}")

        return cls(ipc=ipc,
                   worker=worker,
                   ready_to_shutdown=ready_to_shutdown
                   )

    @staticmethod
    def _camera_manager_worker(ipc: CameraGroupIPC,
                               camera_configs: CameraConfigs,
                               camera_strategy: WorkerStrategy,
                               config_subscription_by_camera: dict[CameraIdString, TopicSubscriptionQueue],
                               shm_subscription_by_camera: dict[CameraIdString, TopicSubscriptionQueue],
                               recording_info_subscription_by_camera: dict[CameraIdString, TopicSubscriptionQueue],
                               ready_to_shutdown: multiprocessing.Value
                               ):
        logger.debug(f"inside _camera_manager_worker")
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

        logger.debug(f"Starting {len(camera_workers)} camera workers...")
        for worker in camera_workers.values():
            logger.debug(f"Starting camera worker for camera ID: {worker.camera_id}")
            worker.start()
            logger.debug(f"Camera worker for camera ID: {worker.camera_id} is alive: {worker.is_alive()}")

        while ipc.should_continue:
            wait_1s()
        logger.debug("Awaiting camera processes to finish...")
        while ipc.camera_orchestrator.any_cameras_alive:
            wait_1s()
        logger.debug("TEMPORARY - Camera Processes Finished")
        for worker in camera_workers.values():
            worker.worker.terminate() #TODO - Die better
        ready_to_shutdown.value = True
        logger.info("Camera manager worker is shut down")

    @property
    def all_ready(self) -> bool:
        return self.ipc.camera_orchestrator.all_cameras_ready

    @property
    def any_alive(self) -> bool:
        return self.ipc.camera_orchestrator.any_cameras_alive

    @property
    def all_alive(self) -> bool:
        return all([not status.closed.value for status in self.ipc.camera_orchestrator.camera_statuses.values()])

    @property
    def cameras_connected(self) -> bool:
        return self.ipc.camera_orchestrator.all_cameras_ready

    def start(self):
        if not self.worker:
            raise ValueError("Camera manager worker not initialized!")

        logger.info("Starting camera manager process...")
        self.worker.start()
        logger.debug("Camera manager worker started.")
        logger.debug(f"Camera manager worker is alive: {self.worker.is_alive()}: {self.worker.pid if isinstance(self.worker, multiprocessing.Process) else None}")
        # logger.debug("\nActive Processes:")
        # for process in multiprocessing.active_children():
        #     logger.debug(f'Process Name: {process.name}, PID: {process.pid}')

        # import threading
        # logger.debug("\nActive Threads:")
        # for thread in threading.enumerate():
        #     logger.debug(f'Thread Name: {thread.name}, ID: {thread.ident}')

    def pause(self, await_paused: bool):
        logger.debug(f"Pausing cameras in camera manager...")
        self.ipc.camera_orchestrator.pause(await_paused=await_paused)

    def unpause(self, await_unpaused: bool):
        logger.debug(f"Unpausing cameras in camera manager...")
        self.ipc.camera_orchestrator.unpause(await_unpaused=await_unpaused)
