import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.frames.wrangling.frame_listener_process import FrameListenerProcess
from skellycam.core.frames.wrangling.frame_router_process import FrameRouterProcess

logger = logging.getLogger(__name__)


class FrameWrangler(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    camera_group_dto: CameraGroupDTO
    listener_process: FrameListenerProcess
    frame_router_process: FrameRouterProcess

    @classmethod
    def create(cls, dto: CameraGroupDTO):
        frame_escape_publisher, frame_escape_subscriber = multiprocessing.Pipe()

        return cls(listener_process=FrameListenerProcess(dto=dto,
                                                         frame_escape_pipe=frame_escape_publisher),

                   frame_router_process=FrameRouterProcess(dto=dto,
                                                           frame_escape_pipe=frame_escape_subscriber),
                   camera_group_dto=dto)

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self.listener_process.start()
        self.frame_router_process.start()

    def is_alive(self) -> bool:
        return self.listener_process.is_alive() and self.frame_router_process.is_alive()

    def join(self):
        self.listener_process.join()
        self.frame_router_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        if not self.camera_group_dto.ipc_flags.kill_camera_group_flag.value == True:
            raise ValueError("FrameWrangler was closed before the kill flag was set.")
        if self.is_alive():
            self.join()
        logger.debug(f"Frame wrangler closed")
