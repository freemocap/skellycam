import logging
import multiprocessing
from dataclasses import dataclass

from pydantic import ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.camera_group_thread import CameraGroupThread
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class CameraGroup:
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Key attributes
    shmorchestrator: CameraGroupSharedMemoryOrchestrator
    camera_group_worker: CameraGroupThread

    # Utility attributes
    dto: CameraGroupDTO
    frame_router_config_queue: multiprocessing.Queue
    frame_listener_config_queue: multiprocessing.Queue
    group_uuid: str

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO):
        shmorchestrator = CameraGroupSharedMemoryOrchestrator.create(camera_group_dto=camera_group_dto,
                                                                     read_only=True)
        frame_router_config_queue = multiprocessing.Queue()
        frame_listener_config_queue = multiprocessing.Queue()
        return cls(dto=camera_group_dto,
                   shmorchestrator=shmorchestrator,
                   frame_router_config_queue=frame_router_config_queue,
                   frame_listener_config_queue=frame_listener_config_queue,
                   camera_group_worker=CameraGroupThread(camera_group_dto=camera_group_dto,
                                                         shmorc_dto=shmorchestrator.to_dto(),
                                                         frame_router_config_queue=frame_router_config_queue,
                                                         frame_listener_config_queue=frame_listener_config_queue),
                   group_uuid=camera_group_dto.group_uuid)

    @property
    def camera_ids(self) -> list[CameraId]:
        return list(self.dto.camera_configs.keys())

    @property
    def camera_configs(self) -> CameraConfigs:
        return self.dto.camera_configs

    @property
    def uuid(self) -> str:
        return self.group_uuid

    def start(self):
        logger.info("Starting camera group")
        self.camera_group_worker.start()

    def close(self):
        logger.debug("Closing camera group")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        if self.camera_group_worker:
            self.camera_group_worker.close()
        self.shmorchestrator.close_and_unlink()
        logger.info("Camera group closed.")

    def update_camera_configs(self,
                              camera_configs: CameraConfigs,
                              update_instructions: UpdateInstructions):
        logger.debug(
            f"Updating Camera Configs with instructions: {update_instructions}")
        self.dto.camera_configs = camera_configs
        self.dto.update_queue.put(update_instructions)
        self.frame_router_config_queue.put(update_instructions.new_configs)
        self.frame_listener_config_queue.put(update_instructions.new_configs)
