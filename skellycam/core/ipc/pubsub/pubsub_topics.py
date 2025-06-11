from typing import Type

from pydantic import Field

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs, ParameterDifferencesModel
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import TopicPublicationQueue, CameraIdString
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel, \
    get_websocket_log_queue


class UpdateCameraSettingsMessage(TopicMessageABC):
    """
    Message sent when a camera configuration update is requested.
    """
    requested_parameter_changes: dict[CameraIdString, list[ParameterDifferencesModel]]
    cameras_to_remove: list[CameraIdString]
    cameras_to_add: list[CameraConfig]

    @classmethod
    def from_configs(cls, current_configs: CameraConfigs, desired_configs: CameraConfigs):
        """
        Create an UpdatedCameraConfigsMessage from old and new camera configurations.
        """

        differences: dict[CameraIdString, list[ParameterDifferencesModel]] = {camera_id: [] for camera_id in
                                                                              current_configs.keys()}
        cameras_to_remove: list[CameraIdString] = []
        cameras_to_add: list[CameraConfig] = []
        for camera_id, current_config in current_configs.items():
            desired_config = desired_configs.get(camera_id)
            if not desired_config or not desired_config.use_this_camera:
                cameras_to_remove.append(camera_id)
            else:
                differences[camera_id] = current_config.get_setting_differences(desired_config)

        for camera_id, desired_config in desired_configs.items():
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
    def need_update_recorder(self) -> bool:
        """
        If the resolution or rotation changed, the recorder needs to be updated.
        """
        return self.need_reset_shm or self.rotation_changed
    @property
    def need_update_mf_builder(self) -> bool:
        """
        If the shm needs to be reset, the multi-frame builder needs to be updated.
        """
        return self.need_reset_shm

    @property
    def only_exposure_changed(self) -> bool:
        """
        If only the exposure settings changed, we can update the cameras without resetting shared memory.
        """
        return not self.need_reset_shm  and self.exposure_changed


class ExtractedConfigMessage(TopicMessageABC):
    """
    Message containing the camera settings extracted from the camera device
    """
    extracted_config: CameraConfig


class NewConfigsMessage(TopicMessageABC):
    """
    Message containing the camera settings extracted from the camera device
    """
    new_configs: CameraConfigs


class UpdateShmMessage(TopicMessageABC):
    group_shm_dto: CameraGroupSharedMemoryDTO
    orchestrator: CameraOrchestrator


class FrontendPayloadMessage(TopicMessageABC):
    frontend_payload: FrontendFramePayload


class RecordingInfoMessage(TopicMessageABC):
    recording_info: RecordingInfo


class UpdateCameraSettingsTopic(PubSubTopicABC):
    message_type: Type[UpdateCameraSettingsMessage] = UpdateCameraSettingsMessage


class ExtractedConfigTopic(PubSubTopicABC):
    message_type: Type[ExtractedConfigMessage] = ExtractedConfigMessage


class NewConfigsTopic(PubSubTopicABC):
    message_type: Type[NewConfigsMessage] = NewConfigsMessage


class ShmUpdatesTopic(PubSubTopicABC):
    message_type: Type[UpdateShmMessage] = UpdateShmMessage


class RecordingInfoTopic(PubSubTopicABC):
    message_type: Type[RecordingInfoMessage] = RecordingInfoMessage


class FrontendPayloadTopic(PubSubTopicABC):
    message_type: Type[FrontendPayloadMessage] = FrontendPayloadMessage


class LogsTopic(PubSubTopicABC):
    message_type: Type[LogRecordModel] = LogRecordModel
    publication: TopicPublicationQueue = Field(default_factory=get_websocket_log_queue)
