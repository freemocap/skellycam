from dataclasses import dataclass
from functools import cached_property
from typing import Type

import numpy as np

from skellylogs import LogRecordModel, get_websocket_log_queue

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.recorders.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
from skellycam.core.types.type_overloads import TopicPublicationQueue, CameraIdString
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO

@dataclass
class DeviceExtractedConfigMessage(TopicMessageABC):
    extracted_config: CameraConfig


@dataclass
class UpdateCamerasSettingsMessage(TopicMessageABC):
    requested_configs: CameraConfigs


@dataclass
class SetShmMessage(TopicMessageABC):
    camera_group_shm_dto: CameraGroupSharedMemoryDTO
    def get_shm_dto_by_camera_id(self, camera_id: CameraIdString) -> SharedMemoryRingBufferDTO:
        return self.camera_group_shm_dto.camera_shm_dtos[camera_id]

@dataclass
class RecordingInfoMessage(TopicMessageABC):
    recording_info: RecordingInfo


@dataclass
class RecordingFinishedMessage(TopicMessageABC):
    recording_info: RecordingInfo
    frame_metadatas: list[np.recarray]

    def __post_init__(self) -> None:
        if not self.frame_metadatas:
            raise ValueError("RecordingFinishedMessage must have at least one frame_metadata.")

        if not all(isinstance(md, np.recarray) for md in self.frame_metadatas):
            raise TypeError("All frame_metadatas must be instances of numpy.recarray.")

        if not all(md.dtype == FRAME_METADATA_DTYPE for md in self.frame_metadatas):
            raise TypeError(f"All frame_metadatas must have dtype {FRAME_METADATA_DTYPE}.")

        first_camera_id = self.frame_metadatas[0].camera_info.camera_id[0]
        if not all(md.camera_info.camera_id[0] == first_camera_id for md in self.frame_metadatas):
            raise ValueError("All frame_metadatas must have the same camera_id.")

        prev_frame_number = self.frame_metadatas[0].frame_number[0] - 1
        for md in self.frame_metadatas:
            if md.frame_number[0] != prev_frame_number + 1:
                raise ValueError("Frame numbers in frame_metadatas must be sequential.")
            prev_frame_number = md.frame_number[0]

    @cached_property
    def camera_id(self) -> CameraIdString:
        return self.frame_metadatas[0].camera_info.camera_id[0]

@dataclass
class FramerateMessage(TopicMessageABC):
    current_framerate: CurrentFramerate


@dataclass
class UpdateCamerasSettingsTopic(PubSubTopicABC):
    message_type: Type[UpdateCamerasSettingsMessage] = UpdateCamerasSettingsMessage


@dataclass
class DeviceExtractedConfigTopic(PubSubTopicABC):
    message_type: Type[DeviceExtractedConfigMessage] = DeviceExtractedConfigMessage


@dataclass
class SetShmTopic(PubSubTopicABC):
    message_type: Type[SetShmMessage] = SetShmMessage



@dataclass
class RecordingInfoTopic(PubSubTopicABC):
    message_type: Type[RecordingInfoMessage] = RecordingInfoMessage


@dataclass
class RecordingFinishedTopic(PubSubTopicABC):
    message_type: Type[RecordingFinishedMessage] = RecordingFinishedMessage


@dataclass
class FramerateTopic(PubSubTopicABC):
    message_type: Type[FramerateMessage] = FramerateMessage


@dataclass
class LogsTopic(PubSubTopicABC):
    message_type: Type[LogRecordModel] = LogRecordModel
    publication: TopicPublicationQueue = None

    def __post_init__(self) -> None:
        if self.publication is None:
            self.publication = get_websocket_log_queue()
