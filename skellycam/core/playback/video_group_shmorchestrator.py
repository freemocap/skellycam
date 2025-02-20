import logging

from pydantic import BaseModel, ConfigDict

from skellycam.core.playback.video_group_dto import VideoGroupDTO
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO

logger = logging.getLogger(__name__)


class VideoGroupSharedMemoryOrchestratorDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO


class VideoGroupSharedMemoryOrchestrator(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    multi_frame_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer

    @classmethod
    def create(cls,
               video_group_dto: VideoGroupDTO,
               read_only: bool):
        return cls(
                   multi_frame_escape_ring_shm=MultiFrameEscapeSharedMemoryRingBuffer.create(camera_group_dto=video_group_dto,
                                                                                       read_only=read_only),
                   )

    @classmethod
    def recreate(cls,
                 video_group_dto: VideoGroupDTO,
                 shmorc_dto: VideoGroupSharedMemoryOrchestratorDTO,
                 read_only: bool):
        return cls(
            multi_frame_escape_ring_shm=MultiFrameEscapeSharedMemoryRingBuffer.recreate(camera_group_dto=video_group_dto,
                                                                                  shm_dto=shmorc_dto.multi_frame_escape_shm_dto,
                                                                                  read_only=read_only),
        )

    @property
    def valid(self):
        return self.multi_frame_escape_ring_shm.valid

    def to_dto(self) -> VideoGroupSharedMemoryOrchestratorDTO:
        return VideoGroupSharedMemoryOrchestratorDTO(multi_frame_escape_shm_dto=self.multi_frame_escape_ring_shm.to_dto())

    def close_and_unlink(self):
        logger.debug("Closing CameraGroupSharedMemoryOrchestrator...")
        self.multi_frame_escape_ring_shm.close_and_unlink()
