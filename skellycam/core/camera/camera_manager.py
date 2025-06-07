import logging
import threading
from dataclasses import dataclass

from skellycam.core.camera.camera_process import CameraProcess
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraSharedMemoryDTOs
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)

MAX_CAMERA_PORTS_TO_CHECK = 20

@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    camera_processes: dict[CameraIdString, CameraProcess]

    @classmethod
    def create_cameras(cls,
                       ipc: CameraGroupIPC,
                       camera_shm_dtos: CameraSharedMemoryDTOs, ):


        camera_processes = {}
        for camera_id, camera_config in ipc.camera_configs.items():
            camera_processes[camera_id] = CameraProcess.create(camera_id=camera_id,
                                                               ipc=ipc,
                                                               camera_shm_dto=camera_shm_dtos[camera_id],
                                                               )

        return cls(ipc=ipc,

                   camera_processes=camera_processes
                   )

    @property
    def orchestrator(self) -> CameraOrchestrator:
        return self.ipc.camera_orchestrator
    @property
    def camera_ids(self):
        return list(self.camera_processes.keys())

    @property
    def paused(self):
        return self.orchestrator.all_cameras_paused


    @property
    def any_alive(self) -> bool:
        return any([process.is_alive() for process in self.camera_processes.values()])

    @property
    def all_alive(self) -> bool:
        return all([process.is_alive() for process in self.camera_processes.values()])

    @property
    def cameras_connected(self) -> bool:
        """
        Check if all cameras in the group are connected.
        """
        return  self.orchestrator.all_cameras_ready




    def start(self):
        if len(self.camera_ids) == 0:
            raise ValueError("No cameras to start!")

        logger.info(f"Starting cameras: {self.camera_ids}...")

        [process.start() for process in self.camera_processes.values()]


    def close_camera(self, camera_id: CameraIdString):
        logger.debug(f"Closing camera: {camera_id}")

        if camera_id not in self.camera_processes:
            raise ValueError(f"Camera {camera_id} does not exist in this group.")

        camera_process = self.camera_processes[camera_id]
        camera_process.close()
        del self.camera_processes[camera_id]

        logger.debug(f"Camera {camera_id} closed successfully.")

    def close(self):
        logger.debug(f"Closing cameras: {self.camera_ids}")

        camera_close_threads = []
        for camera_process in self.camera_processes.values():
            camera_close_threads.append(threading.Thread(target=camera_process.close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]


        while self.any_alive:
            wait_10ms()

        logger.trace(f"Cameras closed: {self.camera_ids}")
