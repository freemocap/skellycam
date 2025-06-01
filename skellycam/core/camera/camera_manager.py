import logging
import threading

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.camera_process import CameraProcess
from skellycam.core.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.shared_memory.camera_group_shared_memory import CameraSharedMemoryDTOs
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)

MAX_CAMERA_PORTS_TO_CHECK = 20



class CameraManager(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    orchestrator: CameraGroupOrchestrator
    ipc: CameraGroupIPC
    camera_processes: dict[CameraIdString, CameraProcess]
    @property
    def camera_ids(self):
        return list(self.camera_processes.keys())

    @classmethod
    def create_cameras(cls,
                       ipc: CameraGroupIPC,
                       camera_shm_dtos: CameraSharedMemoryDTOs,
                       orchestrator: CameraGroupOrchestrator):

        camera_processes = {}
        for camera_id, camera_config in ipc.camera_configs.items():
            camera_processes[camera_id] = CameraProcess.create(camera_id=camera_id,
                                                               ipc=ipc,
                                                               orchestrator=orchestrator,
                                                               camera_shm_dto=camera_shm_dtos[camera_id],
                                                               )

        return cls(ipc=ipc,
                   orchestrator=orchestrator,
                   camera_processes=camera_processes
                   )

    def start(self):
        if len(self.camera_ids) == 0:
            raise ValueError("No cameras to start!")

        logger.info(f"Startingcameras: {self.camera_ids}...")

        [process.start() for process in self.camera_processes.values()]
        logger.info(f"Cameras {self.camera_ids} frame loop ended.")

    def update_camera_configs(self, update_instructions: UpdateInstructions):
        logger.debug(f"Updating cameras with instructions: {update_instructions}")

        for camera_id in update_instructions.update_these_cameras:
            self.camera_processes[camera_id].update_config(update_instructions.new_configs[camera_id])

    def close(self):
        logger.debug(f"Closing cameras: {self.camera_ids}")

        camera_close_threads = []
        for camera_process in self.camera_processes.values():
            camera_close_threads.append(threading.Thread(target=camera_process.close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]

        while any([camera_process.is_alive() for camera_process in self.camera_processes.values()]):
            wait_10ms()

        logger.trace(f"Cameras closed: {self.camera_ids}")
