from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfigs, ParameterDifferencesModel, CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types import CameraIdString


class UpdateCameraSettingsHelper(BaseModel):
    """
    Message sent when a camera configuration update is requested.
    """
    requested_parameter_changes: dict[CameraIdString, list[ParameterDifferencesModel]]
    cameras_to_remove: list[CameraIdString]
    cameras_to_add: list[CameraConfig]

    @classmethod
    def from_configs(cls, current_configs: CameraConfigs, requested_configs: CameraConfigs):

        differences: dict[CameraIdString, list[ParameterDifferencesModel]] = {camera_id: [] for camera_id in
                                                                              current_configs.keys()}
        cameras_to_remove: list[CameraIdString] = []
        cameras_to_add: list[CameraConfig] = []
        for camera_id, current_config in current_configs.items():
            desired_config = requested_configs.get(camera_id)
            if not desired_config or not desired_config.use_this_camera:
                cameras_to_remove.append(camera_id)
            else:
                differences[camera_id] = current_config.get_setting_differences(desired_config)

        for camera_id, desired_config in requested_configs.items():
            if camera_id not in current_configs:
                cameras_to_add.append(desired_config)

        return cls(
            requested_parameter_changes=differences,
            cameras_to_remove=cameras_to_remove,
            cameras_to_add=cameras_to_add,
        )
    @property
    def any_settings_changes(self) -> bool:
        return not any([len(changes)>0 for changes in self.requested_parameter_changes.values()])

    @property
    def need_update_configs(self) -> bool:
        return any([self.any_settings_changes or self.cameras_to_remove or self.cameras_to_add])

    @property
    def resolution_changed(self) -> bool:
        resolution_changed = False
        for camera_id, differences in self.requested_parameter_changes.items():
            for difference in differences:
                if difference.parameter_name == "resolution":
                    resolution_changed = True
                    break
            if resolution_changed:
                break
        return resolution_changed

    @property
    def rotation_changed(self) -> bool:
        rotation_changed = False
        for camera_id, differences in self.requested_parameter_changes.items():
            for difference in differences:
                if difference.parameter_name == "rotation":
                    rotation_changed = True
                    break
            if rotation_changed:
                break
        return rotation_changed

    @property
    def exposure_changed(self) -> bool:
        exposure_changed = False
        for camera_id, differences in self.requested_parameter_changes.items():
            for difference in differences:
                if difference.parameter_name == "exposure" or difference.parameter_name == "exposure_mode":
                    exposure_changed = True
                    break
            if exposure_changed:
                break
        return exposure_changed

    @property
    def need_reset_shm(self) -> bool:
        """
        If the image shape changed or if cameras were added or removed, the shared memory needs to be reset.
        """
        return self.cameras_to_remove or self.cameras_to_add or self.resolution_changed

    @property
    def only_exposure_changed(self) -> bool:
        """
        If only the exposure settings changed, we can update the cameras without resetting shared memory.
        """
        return not self.need_reset_shm and not self.rotation_changed and self.exposure_changed



def update_camera_group(camera_group:CameraGroup,
                        requested_configs:CameraConfigs) -> CameraGroup:
    update_helper = UpdateCameraSettingsHelper.from_configs(
        current_configs=camera_group.configs,
        requested_configs=requested_configs
    )

    if update_helper.need_reset_shm:
        # TODO - update the shm without resetting the whole shebang
        camera_group.close()
        return CameraGroup.create_and_start(
            group_id = camera_group.id,
            camera_configs=requested_configs,
            global_kill_flag=camera_group.ipc.global_kill_flag
        )

    camera_group.update_camera_settings(requested_configs=requested_configs)
    return camera_group


