import logging
import multiprocessing
from typing import Optional

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_process import CameraGroupProcess
from skellycam.core.cameras.group.update_instructions import UpdateInstructions
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            cgp_group_shm_dto: CameraGroupSharedMemoryDTO,
            shm_valid_flag: multiprocessing.Value,
            camera_configs: CameraConfigs,
            ipc_queue: multiprocessing.Queue,
            record_frames_flag: multiprocessing.Value,
            global_kill_event: multiprocessing.Event,
    ):
        self._kill_camera_group_flag = multiprocessing.Value('b', False)
        self._update_queue = multiprocessing.Queue()  # Update camera configs
        self._ipc_queue = ipc_queue



        self._camera_group_process = CameraGroupProcess(group_shm_dto=cgp_group_shm_dto,
                                                        shm_valid_flag=shm_valid_flag,
                                                        camera_configs=camera_configs,
                                                        config_update_queue=self._update_queue,
                                                        ipc_queue=self._ipc_queue,
                                                        kill_camera_group_flag=self._kill_camera_group_flag,
                                                        global_kill_event=global_kill_event,
                                                        record_frames_flag=record_frames_flag,
                                                        )

    async def start(self, number_of_frames: Optional[int] = None):
        logger.info("Starting camera group")
        await self._camera_group_process.start()

    async def close(self):
        logger.debug("Closing camera group")
        self._kill_camera_group_flag.value = True
        if self._camera_group_process:
            await self._camera_group_process.close()
        logger.info("Camera group closed.")

    async def update_camera_configs(self,
                                    update_instructions: UpdateInstructions):
        logger.debug(
            f"Updating Camera Configs with instructions: {update_instructions}")
        self._update_queue.put(update_instructions)


