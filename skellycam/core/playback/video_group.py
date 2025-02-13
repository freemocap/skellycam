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

logger = logging.getLogger(__name__)

""" 
TODO:
Do we need a process VideoGroupThread/Process?
I think this will somehow run the video_playback class, and that probably wants to run in its own thread.
But how do we want it to run? 

"""

@dataclass
class VideoGroup:
    dto: VideoGroupDTO
    camera_group_process: CameraGroupThread
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
                   camera_group_process=CameraGroupThread(camera_group_dto=video_group_dto,
                                                          shmorc_dto=shmorc_dto,
                                                          frame_router_config_queue=frame_router_config_queue,
                                                          frame_listener_config_queue=frame_listener_config_queue),
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
        self.camera_group_process.start()

    def close(self):
        logger.debug("Closing video group")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        if self.camera_group_process:
            self.camera_group_process.close()
        logger.info("video group closed.")
