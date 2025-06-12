from typing import Type

from pydantic import Field

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import TopicPublicationQueue
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel, \
    get_websocket_log_queue


class DeviceExtractedConfigMessage(TopicMessageABC):
    extracted_config: CameraConfig

class UpdateCamerasSettingsMessage(TopicMessageABC):
    requested_configs: CameraConfigs

class SetShmMessage(TopicMessageABC):
    camera_group_shm_dto: CameraGroupSharedMemoryDTO

class RecordingInfoMessage(TopicMessageABC):
    recording_info: RecordingInfo


class UpdateCamerasSettingsTopic(PubSubTopicABC):
    message_type: Type[UpdateCamerasSettingsMessage] = UpdateCamerasSettingsMessage

class DeviceExtractedConfigTopic(PubSubTopicABC):
    message_type: Type[DeviceExtractedConfigMessage] = DeviceExtractedConfigMessage

class SetShmTopic(PubSubTopicABC):
    message_type: Type[SetShmMessage] = SetShmMessage

class RecordingInfoTopic(PubSubTopicABC):
    message_type: Type[RecordingInfoMessage] = RecordingInfoMessage


class LogsTopic(PubSubTopicABC):
    message_type: Type[LogRecordModel] = LogRecordModel
    publication: TopicPublicationQueue = Field(default_factory=get_websocket_log_queue)
