from pydantic import Field
from typing import Type

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.recorders.videos.recording_info import RecordingInfo


class UpdateCameraConfigsMessage(TopicMessageABC):
    """
    Message sent when a camera configuration update is requested.
    """
    old_configs: CameraConfigs
    new_configs: CameraConfigs
    close_these_cameras: list[CameraConfig]
    new_cameras: list[CameraConfig]

    @classmethod
    def from_configs(cls, old_configs: CameraConfigs, new_configs: CameraConfigs):
        """
        Create an UpdatedCameraConfigsMessage from old and new camera configurations.
        """
        need_update_configs = False
        new_cameras: list[CameraConfig] = []
        close_these_cameras: list[CameraConfig] = []

        for new_config in new_configs.values():
            if not new_config.camera_id in old_configs:
                new_cameras.append(new_config)
            if not new_config.use_this_camera:
                close_these_cameras.append(new_config)

        for old_config in old_configs.values():
            if not old_config.camera_id in new_configs:
                close_these_cameras.append(old_config)
        return cls(
            old_configs=old_configs,
            new_configs=new_configs,
            close_these_cameras=close_these_cameras,
            new_cameras=new_cameras
        )
    @property
    def need_reset_shm(self) -> bool:
        need_reset_shm = self.close_these_cameras or self.new_cameras

        for new_config in self.new_configs.values():
            if new_config.image_shape != self.old_configs[new_config.camera_id].image_shape:
                need_reset_shm = True
        return need_reset_shm

    @property
    def need_update_configs(self) -> bool:
        """
        Check if the camera configurations need to be updated.
        """
        return self.old_configs != self.new_configs or self.close_these_cameras or self.new_cameras

    @property
    def only_exposure_changed(self) -> bool:
        new_configs_without_exposure = {camera_id: CameraConfig(**config.model_dump(exclude={'exposure', 'exposure_mode'})) for camera_id, config in self.new_configs}
        old_configs_without_exposure = {camera_id: CameraConfig(**config.model_dump(exclude={'exposure', 'exposure_mode'})) for camera_id, config in self.old_configs}
        return new_configs_without_exposure == old_configs_without_exposure

class ExtractedConfigMessage(TopicMessageABC):
    """
    Message containing the camera settings extracted from the camera device
    """
    extracted_config: CameraConfig


class ShmUpdateMessage(TopicMessageABC):
    orchestrator: CameraOrchestrator|None = None
    group_shm_dto: CameraGroupSharedMemoryDTO|None = None


class RecordingInfoMessage(TopicMessageABC):
    recording_info: RecordingInfo


class UpdateConfigsTopic(PubSubTopicABC):
    message_type: Type[UpdateCameraConfigsMessage] = UpdateCameraConfigsMessage

class ExtractedConfigTopic(PubSubTopicABC):
    message_type: Type[ExtractedConfigMessage] = ExtractedConfigMessage

class ShmUpdatesTopic(PubSubTopicABC):
    message_type: Type[ShmUpdateMessage] = ShmUpdateMessage

class RecordingInfoTopic(PubSubTopicABC):
    message_type: Type[RecordingInfoMessage] = RecordingInfoMessage
