import logging
from dataclasses import dataclass

from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.types import CameraIdString, WorkerStrategy
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    camera_processes: dict[CameraIdString, CameraWorker]

    @classmethod
    def create_cameras(cls,
                       ipc: CameraGroupIPC,
                       camera_configs: CameraConfigs,
                       worker_strategy: WorkerStrategy):


        camera_processes = {}
        for camera_id, camera_config in camera_configs.items():
            camera_processes[camera_id] = CameraWorker.create(camera_id=camera_id,
                                                              ipc=ipc,
                                                              config=camera_config,
                                                              worker_strategy=worker_strategy
                                                              )

        return cls(ipc=ipc, camera_processes=camera_processes)


    @property
    def camera_ids(self):
        return list(self.camera_processes.keys())

    @property
    def any_alive(self) -> bool:
        return any([process.is_alive() for process in self.camera_processes.values()])

    @property
    def all_ready(self) -> bool:
        return self.ipc.camera_orchestrator.all_cameras_ready

    @property
    def all_alive(self) -> bool:
        return all([process.is_alive() for process in self.camera_processes.values()])

    @property
    def cameras_connected(self) -> bool:
        """
        Check if all cameras in the group are connected.
        """
        return self.ipc.camera_orchestrator.all_cameras_ready

    def start(self):
        if len(self.camera_ids) == 0:
            raise ValueError("No cameras to start!")

        logger.info(f"Starting cameras: {self.camera_ids}...")

        [process.start() for process in self.camera_processes.values()]

    def pause(self, await_paused: bool):
        logger.debug(f"Pausing cameras: {self.camera_ids}")
        for status in self.ipc.camera_orchestrator.camera_statuses.values():
            status.should_pause.value = True
        if await_paused:
            while not self.ipc.camera_orchestrator.all_cameras_paused:
                wait_10ms()
        logger.debug(f"Cameras paused: {self.camera_ids}")

    def unpause(self, await_unpaused: bool = True):
        logger.debug(f"Unpausing cameras: {self.camera_ids}")
        for status in self.ipc.camera_orchestrator.camera_statuses.values():
            status.should_pause.value = False
        if await_unpaused:
            while self.ipc.camera_orchestrator.any_cameras_paused:
                wait_10ms()
        logger.debug(f"Cameras unpaused: {self.camera_ids}")

    def close(self):
        logger.debug(f"Closing cameras: {self.camera_ids}")

        for camera_process in self.camera_processes.values():
            camera_process.close()
        for camera_process in self.camera_processes.values():
            camera_process.join()

        logger.trace(f"Cameras closed: {self.camera_ids}")
