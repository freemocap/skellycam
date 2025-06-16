import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.types.type_overloads import WorkerStrategy, WorkerType
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    worker: WorkerType
    close_self_flag: multiprocessing.Value

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               camera_configs: CameraConfigs,
               camera_manager_strategy: WorkerStrategy,
               camera_strategy: WorkerStrategy):

        close_self_flag = multiprocessing.Value("b", False)

        worker = camera_manager_strategy.value(
            target=cls._camera_manager_worker,
            name=f"{cls.__name__}-Worker",
            daemon=True,
            kwargs=dict(
                ipc=ipc,
                camera_configs=camera_configs,
                close_self_flag=close_self_flag,
                camera_strategy=camera_strategy,
            )
        )

        return cls(ipc=ipc,
                   worker=worker,
                   close_self_flag=close_self_flag)

    @staticmethod
    def _camera_manager_worker(ipc: CameraGroupIPC,
                               camera_configs: CameraConfigs,
                               close_self_flag: multiprocessing.Value,
                               camera_strategy: WorkerStrategy,
                               ):
        logger.info(f"Starting camera manager process with {len(camera_configs)} cameras")


        camera_processes = {}

        for camera_id, camera_config in camera_configs.items():
            camera_processes[camera_id] = CameraWorker.create(
                camera_id=camera_id,
                ipc=ipc,
                config=camera_config,
                worker_strategy=camera_strategy,
            )

        for process in camera_processes.values():
            process.start()

        while not close_self_flag.value:
            wait_10ms()

        logger.info("Camera manager worker closing all camera workers")
        for camera_process in camera_processes.values():
            camera_process.close()
        for camera_process in camera_processes.values():
            camera_process.join()

        logger.info("Camera manager worker exiting")


    def close(self):
        if not self.worker:
            raise ValueError("Camera manager worker not initialized!")

        logger.info("Closing camera manager process...")
        self.close_self_flag.value = True
        self.worker.join()
        logger.info("Camera manager worker closed.")

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
