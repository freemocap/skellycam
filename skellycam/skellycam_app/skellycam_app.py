import logging
import multiprocessing
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraGroupIdString
from skellycam.skellycam_app.skellycam_app_ipc.ipc_manager import InterProcessCommunicationManager
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue

logger = logging.getLogger(__name__)





@dataclass
class SkellycamApplication:
    global_kill_flag: multiprocessing.Value
    camera_group_manager: CameraGroupManager


    @classmethod
    def initialize_skellycam_app(cls, global_kill_flag: multiprocessing.Value):
        return cls(global_kill_flag=global_kill_flag,
                     camera_group_manager=CameraGroupManager(global_kill_flag=global_kill_flag))

    @property
    def should_continue(self) -> bool:
        """
        Check if the application should continue running.
        """
        return not self.global_kill_flag.value

    def create_camera_group(self, camera_configs: CameraConfigs) -> CameraGroupIdString:

        logger.info(f"Creating camera group with cameras: {list(camera_configs.keys())}")
        camera_group_id = self.camera_group_manager.create_camera_group(camera_configs=camera_configs)
        self.camera_group_manager.get_camera_group(camera_group_id).start()
        logger.info(f"Camera group created with ID: {camera_group_id} and cameras: {list(camera_configs.keys())}")
        return camera_group_id

    def get_new_frontend_payloads(self, if_newer_than:int|None) -> list[FrontendFramePayload]:
        return self.camera_group_manager.get_latest_frontend_payloads(if_newer_than=if_newer_than)
    
    def update_camera_configs(self,
                              camera_configs: CameraConfigs | CameraConfig | list[CameraConfig]):
        if isinstance(camera_configs, CameraConfig):
            camera_configs = {camera_configs.camera_id: camera_configs}
        elif isinstance(camera_configs, list):
            camera_configs = {config.camera_id: config for config in camera_configs}
        for camera_id, camera_config in camera_configs.items():
            self.camera_group_manager.update_camera_settings(camera_config=camera_config)

    def close_all_camera_groups(self):
        self.camera_group_manager.close_all_camera_groups()
        logger.success("Camera groups closed successfully")

    def start_recording(self, recording_info: RecordingInfo):
        self.camera_group_manager.start_recording_all_groups(recording_info=recording_info)

    def stop_recording(self):
        self.camera_group_manager.stop_recording_all_groups()

    def state_dto(self):
        return SkellycamAppStateDTO.from_state(self)

    def shutdown_skellycam(self):
        self.global_kill_flag.value = True
        self.camera_group_manager.close_all_camera_groups()


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
