import logging
import multiprocessing
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraIdString, CameraGroupIdString
from skellycam.skellycam_app.skellycam_app_ipc.ipc_manager import InterProcessCommunicationManager

logger = logging.getLogger(__name__)


@dataclass
class SkellycamApplication:
    ipc: InterProcessCommunicationManager
    camera_group_manager: CameraGroupManager = field(default_factory=CameraGroupManager)


    @classmethod
    def initialize_skellycam_app(cls, global_kill_flag: multiprocessing.Value):
        return cls(ipc=InterProcessCommunicationManager(global_kill_flag=global_kill_flag))

    # @property
    # def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer| None:
    #     if not self.camera_group:
    #         return None
    #     return self.camera_group.multi_frame_escape_ring_shm
    #
    #
    # @property
    # def camera_group_configs(self) -> CameraConfigs | None:
    #     if self.camera_group is None:
    #         return  None
    #     return self.camera_group.camera_configs
    #
    # def create_camera_group(self,
    #                         camera_configs: CameraConfigs):
    #     if self.camera_group is None:
    #         self.create_camera_group(camera_configs=camera_configs)
    #     else:
    #         self.update_camera_group(camera_configs=camera_configs)

    def create_camera_group(self, camera_configs: CameraConfigs)-> CameraGroupIdString:

        logger.info(f"Creating camera group with cameras: {list(camera_configs.keys())}")
        camera_group_id = self.camera_group_manager.create_camera_group(camera_configs=camera_configs)
        self.camera_group_manager.get_camera_group(camera_group_id).start()
        logger.info(f"Camera group created with ID: {camera_group_id} and cameras: {list(camera_configs.keys())}")
        return camera_group_id

    def set_device_extracted_camera_configs(self, configs: CameraConfigs):
        if self.camera_group is None or self.camera_group.camera_configs is None:
            raise ValueError("Cannot set device extracted camera config without CameraGroup!")
        self.camera_group.camera_configs.update(configs)
        self.ipc.ws_ipc_relay_queue.put(self.state_dto())

    def update_camera_group(self,
                            camera_configs: CameraConfigs):
        if self.camera_group is None or self.camera_group.camera_configs is None:
            raise ValueError("Cannot update CameraGroup if it does not exist!")
        update_instructions = UpdateInstructions.from_configs(new_configs=camera_configs,
                                                              old_configs=self.camera_group.camera_configs)
        logger.trace(f"Camera Config Update instructions: {update_instructions}")
        self.camera_group.update_camera_configs(camera_configs=camera_configs,
                                                update_instructions=update_instructions)

    def close_all_camera_groups(self):
        self.camera_group_manager.close_all_camera_groups()
        logger.success("Camera groups closed successfully")

    def start_recording(self, recording_info: RecordingInfo):
        if self.camera_group is None:
            raise ValueError("Cannot start recording without CameraGroup!")
        if self.ipc.record_frames_flag.value:
            raise ValueError("Cannot start recording when already recording!")
        self.ipc.start_recording_queue.put(recording_info)

        self.ipc.ws_ipc_relay_queue.put(self.state_dto())

    def stop_recording(self):
        self.ipc.record_frames_flag.value = False
        self.ipc.ws_ipc_relay_queue.put(self.state_dto())

    def state_dto(self):
        return SkellycamAppStateDTO.from_state(self)

    def _reset(self):
        if self.camera_group:
            self.close_camera_group()
        if self.shmorchestrator:
            self.shmorchestrator.close_and_unlink()
        self.camera_group = None
        self.shmorchestrator = None
        self.ipc = InterProcessCommunicationManager(global_kill_flag=self.ipc.global_kill_flag)

    def shutdown_skellycam(self):
        self.ipc.global_kill_flag.value = True
        if self.camera_group:
            self.close_camera_group()


class SkellycamAppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the SkellycamAppState
    """
    type: str
    state_timestamp: str = datetime.now().isoformat()

    camera_configs: CameraConfigs | None
    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: SkellycamApplication):
        return cls(
            camera_configs=state.camera_group.camera_configs if state.camera_group else None,
            record_frames_flag_status=state.ipc.record_frames_flag.value,
            type=cls.__name__
        )


SKELLYCAM_APP_STATE: Optional[SkellycamApplication] = None


def create_skellycam_app(global_kill_flag: multiprocessing.Value,
                         ) -> SkellycamApplication:
    global SKELLYCAM_APP_STATE
    if not SKELLYCAM_APP_STATE:
        SKELLYCAM_APP_STATE = SkellycamApplication.initialize_skellycam_app(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("SkellycamAppState already exists!")
    return SKELLYCAM_APP_STATE


def get_skellycam_app() -> SkellycamApplication:
    global SKELLYCAM_APP_STATE
    if SKELLYCAM_APP_STATE is None:
        raise ValueError("SkellycamAppState does not exist!")
    return SKELLYCAM_APP_STATE
