from dataclasses import dataclass
import logging
import multiprocessing

from skellycam.core import CameraId
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.camera_group_process import CameraGroupThread
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.playback.video_config import VideoConfigs
from skellycam.core.playback.video_group_dto import VideoGroupDTO
from skellycam.core.playback.video_group_thread import VideoGroupThread

logger = logging.getLogger(__name__)


@dataclass
class VideoGroup:
    dto: VideoGroupDTO
    video_group_thread: VideoGroupThread
    frame_router_config_queue: multiprocessing.Queue
    frame_listener_config_queue: multiprocessing.Queue
    group_uuid: str

    @classmethod
    def create(cls,
               video_group_dto: VideoGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO):
        # TODO: figure out what to use for shmorchestrator
        # TODO: rewrite CameraGroupThread as VideoGroupThread
        frame_router_config_queue = multiprocessing.Queue()
        frame_listener_config_queue = multiprocessing.Queue()
        return cls(dto=video_group_dto,
                   video_group_thread=VideoGroupThread(video_group_dto=video_group_dto,
                                                         multi_frame_escape_shm_dto=shmorc_dto.multi_frame_escape_shm_dto),
                   frame_router_config_queue=frame_router_config_queue,
                   frame_listener_config_queue=frame_listener_config_queue,
                   group_uuid=video_group_dto.group_uuid)

    @property
    def video_ids(self) -> list[CameraId]:
        return list(self.dto.video_configs.keys())

    @property
    def video_configs(self) -> VideoConfigs:
        return self.dto.video_configs

    @property
    def uuid(self) -> str:
        return self.group_uuid

    def start(self):
        logger.info("Starting video group")
        self.video_group_thread.start()

    def close(self):
        logger.debug("Closing video group")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        if self.video_group_thread:
            self.video_group_thread.close()
        logger.info("video group closed.")
