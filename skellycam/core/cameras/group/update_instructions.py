from typing import List

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_process import logger


class UpdateInstructions(BaseModel):
    """
    Update instructions for CameraGroupProcess

    - NOTE - If any existing camera's resolution changed or any new cameras added, we reset the whole thing

    Will need to update:
    - CameraGroupOrchestrator: delete unused cameras
    - CameraGroupSharedMemory: delete unused cameras
    - CameraManager: delete unused, update existing if config changed

    """
    new_configs: CameraConfigs
    reset_all: bool  # If True, reset all cameras (e.g. if resolution changed, new cameras added, or user requested `reset`)
    close_these_cameras: List[CameraId] = Field(
        default_factory=list)  # close these cameras and remove from orchestrator and shared memory
    # create: List[CameraId] = Field(default_factory=list) #TODO - support creating new cams w/o reset (requires handling shm recreation)
    update_these_cameras: List[CameraId] = Field(default_factory=list)

    @classmethod
    def reset_all(cls, configs: CameraConfigs):
        # Reset all cameras using specified configs
        return cls(new_configs=configs, reset_all=True)

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
        ### Step 1b - if any new cameras added, reset all
        for camera_id, config in new_configs.items():
            if camera_id not in old_configs.keys():
                logger.trace(f"Camera: {camera_id} is new - Setting `reset_all` to True")
                reset_all = True
            else:
                if new_configs[camera_id].use_this_camera:
                    logger.trace(f"Camera {camera_id} needs to be created - Setting `reset_all` to True")
                    reset_all = True
        if reset_all:
            return cls.reset_all(new_configs)

        ## Step 2 (if not resetting everything) - Determine which cameras to close
        cameras_to_close = []
        cameras_to_update = []
        for camera_id in old_configs.keys():
            if camera_id not in new_configs:
                logger.trace(f"Camera {camera_id} not specified in new configs, marking for closure")
                cameras_to_close.append(camera_id)
            else:
                ### Case2 - if a camera exists in `new_configs`, but `use_this_camera` is False, stop the camera
                if not new_configs[camera_id].use_this_camera:
                    logger.trace(f"Camera {camera_id} marked as not to be used in new configs, marking for closure")
                    cameras_to_close.append(camera_id)

        ## Step 3 -  Determine which cameras to update
        for camera_id, config in old_configs.items():
            if camera_id in new_configs:
                if new_configs[camera_id] != config:
                    logger.trace(f"Camera {camera_id} configuration changed, marking for update")
                    cameras_to_update.append(camera_id)

        return cls(new_configs=new_configs,
                   close_these_cameras=cameras_to_close,
                   update_these_cameras=cameras_to_update)
