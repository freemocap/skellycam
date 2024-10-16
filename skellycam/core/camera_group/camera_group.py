import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.camera_group_process import CameraGroupProcess

logger = logging.getLogger(__name__)


class CameraGroup(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dto: CameraGroupDTO
    camera_group_process: Optional[CameraGroupProcess] = None

    @classmethod
    def create(cls, dto: CameraGroupDTO):
        return cls(dto=dto, camera_group_process=CameraGroupProcess(dto=dto))

    @property
    def camera_ids(self):
        return list(self.dto.camera_configs.keys())

    def start(self):
        logger.info("Starting camera group")
        self.camera_group_process.start()

    async def close(self):
        logger.debug("Closing camera group")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        if self.camera_group_process:
            await self.camera_group_process.close()
        logger.info("Camera group closed.")

    async def update_camera_configs(self,
                                    camera_configs: CameraConfigs,
                                    update_instructions: UpdateInstructions):
        logger.debug(
            f"Updating Camera Configs with instructions: {update_instructions}")
        self.dto.update_camera_configs(camera_configs)
        self.dto.config_update_queue.put(update_instructions)
