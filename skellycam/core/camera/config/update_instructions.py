import logging
from typing import List

from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


class UpdateInstructions(BaseModel):
    """
    Update instructions for CameraGroupProcess

    - NOTE - If any existing camera's resolution changed or cameras added/removed, we reset the whole thing

    Will need to update:
    - CameraManager: update existing if config changed

    """
    new_configs: CameraConfigs
    reset_all: bool  # If True, reset all cameras (e.g. if resolution changed, new cameras added, or user requested `reset`)
    # close_these_cameras: List[CameraId] = Field(
    #     default_factory=list)  # TODO - support closing cameras w/o reset (requires handling shm deletion and camera process deletion)
    # create: List[CameraId] = Field(default_factory=list) #TODO - support creating new cams w/o reset (requires handling shm recreation)
    update_these_cameras: List[CameraIdString] = Field(default_factory=list)


    @classmethod
    def from_configs(cls,
                     new_configs: CameraConfigs,
                     old_configs: CameraConfigs):

        ## Step 1 - determine if we need to reset all cameras
        reset_all = False
        ### Step 1a - if any camera's resolution changed, reset all
        for camera_id, config in new_configs.items():
            if camera_id in old_configs.keys():
                if new_configs[camera_id].resolution != old_configs[camera_id].resolution:
                    logger.trace(f"Camera {camera_id} resolution changed - Setting `reset_all` to True")
                    reset_all = True

                # if new_configs[camera_id].rotation != old_configs[camera_id].rotation:
                #     logger.trace(f"Camera {camera_id} rotation changed - Setting `reset_all` to True")
                #     reset_all = True

        ### Step 1b - if any new cameras added or disabled, reset all
        for camera_id, config in new_configs.items():
            if camera_id not in old_configs.keys():
                logger.trace(f"Camera: {camera_id} is new - Setting `reset_all` to True")
                reset_all = True
            else:
                if not new_configs[camera_id].use_this_camera:
                    logger.trace(f"Camera {camera_id} needs to be created - Setting `reset_all` to True")
                    reset_all = True
        ### Step 1c - if any cameras removed, reset all
        for camera_id, config in old_configs.items():
            if camera_id not in new_configs.keys():
                logger.trace(f"Camera {camera_id} removed - Setting `reset_all` to True")
                reset_all = True

        if reset_all:
            return cls.reset_camera_group(new_configs)

        ## Step 3 -  Determine which cameras to update
        cameras_to_update = []

        for camera_id, config in old_configs.items():
            if camera_id in new_configs:
                if new_configs[camera_id] != config:
                    logger.trace(f"Camera {camera_id} configuration changed, marking for update")
                    cameras_to_update.append(camera_id)

        return cls(reset_all=reset_all,
                   new_configs=new_configs,
                   update_these_cameras=cameras_to_update)

    @classmethod
    def reset_camera_group(cls, configs: CameraConfigs):
        # Reset all cameras using specified configs
        return cls(new_configs=configs, reset_all=True)
