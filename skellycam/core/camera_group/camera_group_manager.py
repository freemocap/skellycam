import logging
from dataclasses import dataclass, field

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.types import CameraGroupIdString

logger = logging.getLogger(__name__)

@dataclass
class CameraGroupManager:
    camera_groups: dict[CameraGroupIdString, CameraGroup] = field(default_factory=dict)

    def create_camera_group(self, camera_configs:CameraConfigs) -> CameraGroupIdString:
        """
        Create a camera group with the provided configuration settings.
        """
        camera_group = CameraGroup.from_configs(camera_configs = camera_configs)
        self.camera_groups[camera_group.group_id] = camera_group
        logger.info(f"Creating camera group with ID: {camera_group.id} and cameras: {camera_group.camera_configs.keys()}")
        return camera_group

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> CameraGroup:
        """
        Retrieve a camera group by its ID.
        """
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        return self.camera_groups[camera_group_id]

    def update_camera_config(self, camera_config:CameraConfig):
        for camera_group in self.camera_groups.values():
            if camera_config.camera_id in camera_group.camera_configs:
                camera_group.update_camera_config(camera_config)
                logger.info(f"Updated camera config for camera ID: {camera_config.camera_id} in group ID: {camera_group.id}")

    def close_camera_group(self, camera_group_id: CameraGroupIdString) -> None:
        """
        Remove a camera group by its ID.
        """
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        camera_group = self.camera_groups.pop(camera_group_id)
        camera_group.close()
        logger.info(f"Closed camera group with ID: {camera_group_id}")

    def close_all_camera_groups(self) -> None:
        """
        Close all camera groups.
        """
        for camera_group_id in list(self.camera_groups.keys()):
            self.close_camera_group(camera_group_id)
        logger.info("Closed all camera groups.")

