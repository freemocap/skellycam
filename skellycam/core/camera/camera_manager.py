import logging
from dataclasses import dataclass

from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraSharedMemoryDTOs
from skellycam.core.ipc.shared_memory.single_slot_camera_shared_memory import CameraSharedMemoryDTO
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)

MAX_CAMERA_PORTS_TO_CHECK = 20


@dataclass
class CameraManager:
    ipc: CameraGroupIPC
    orchestrator: CameraOrchestrator
    camera_processes: dict[CameraIdString, CameraWorker]

    @classmethod
    def create_cameras(cls,
                       ipc: CameraGroupIPC,
                       camera_configs: CameraConfigs,
                       camera_shm_dtos: CameraSharedMemoryDTOs, ):
        camera_orchestrator = CameraOrchestrator.from_camera_ids(camera_ids=list(camera_configs.keys()))

        camera_processes = {}
        for camera_id, camera_config in camera_configs.items():
            camera_processes[camera_id] = CameraWorker.create(camera_id=camera_id,
                                                               orchestrator=camera_orchestrator,
                                                               ipc=ipc,
                                                               camera_shm_dto=camera_shm_dtos[camera_id],
                                                               config=camera_config
                                                               )

        return cls(ipc=ipc,
                   camera_processes=camera_processes,
                   orchestrator=camera_orchestrator
                   )

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
        return self.orchestrator.all_cameras_ready

    def start(self):
        if len(self.camera_ids) == 0:
            raise ValueError("No cameras to start!")

        logger.info(f"Starting cameras: {self.camera_ids}...")

        [process.start() for process in self.camera_processes.values()]

    def add_new_camera(self,
                       camera_id: CameraIdString,
                       ipc: CameraGroupIPC,
                       camera_shm_dto: CameraSharedMemoryDTO):
        logger.debug(f"Adding new camera: {camera_id}")
        self.camera_processes[camera_id] = CameraWorker.create(camera_id=camera_id,
                                                                ipc=ipc,
                                                                camera_shm_dto=camera_shm_dto,
                                                                )
        self.camera_processes[camera_id].start()

    def remove_camera(self, camera_id: CameraIdString):
        logger.debug(f"Closing camera: {camera_id}")

        if camera_id not in self.camera_processes:
            raise ValueError(f"Camera {camera_id} does not exist in this group.")

        self.camera_processes[camera_id].close()
        self.camera_processes[camera_id].join()
        del self.camera_processes[camera_id]

        logger.debug(f"Camera {camera_id} closed successfully.")

    def close(self):
        logger.debug(f"Closing cameras: {self.camera_ids}")

        for camera_process in self.camera_processes.values():
            camera_process.close()
        for camera_process in self.camera_processes.values():
            camera_process.join()

        logger.trace(f"Cameras closed: {self.camera_ids}")
