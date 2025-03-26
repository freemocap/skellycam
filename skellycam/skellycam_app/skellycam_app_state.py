import logging
import multiprocessing
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import CameraGroupSharedMemoryOrchestrator
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_shared_memory import \
    RingBufferCameraSharedMemory
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.skellycam_app.skellycam_app_controller.ipc_flags import IPCFlags
from skellycam.system.device_detection.camera_device_info import AvailableCameras, \
    available_cameras_to_default_camera_configs
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue

logger = logging.getLogger(__name__)


@dataclass
class SkellycamAppState:
    ipc_flags: IPCFlags
    ipc_queue: multiprocessing.Queue
    logs_queue: multiprocessing.Queue
    camera_group_update_queue: multiprocessing.Queue

    shmorchestrator: CameraGroupSharedMemoryOrchestrator | None = None
    camera_group: CameraGroup | None = None
    available_cameras: AvailableCameras | None = None
    backend_framerate: CurrentFramerate | None = None
    frontend_framerate: CurrentFramerate | None = None

    @classmethod
    def create(cls,
               global_kill_flag: multiprocessing.Value,
               ) -> "SkellycamAppState":
        return cls(ipc_flags=IPCFlags(global_kill_flag=global_kill_flag),
                   ipc_queue=multiprocessing.Queue(),
                   logs_queue=get_websocket_log_queue(),
                   camera_group_update_queue=multiprocessing.Queue())

    @property
    def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer| None:
        if not self.camera_group:
            return None
        return self.camera_group.multi_frame_escape_ring_shm

    @property
    def camera_ring_buffer_shms(self) -> dict[CameraId, RingBufferCameraSharedMemory]:
        if self.camera_group is None:
            raise ValueError("Cannot get RingBufferCameraSharedMemory without CameraGroup!")
        return {camera_id: RingBufferCameraSharedMemory.create(camera_config=config,
                                                               memory_allocation=100_000_000,  # 100 MB per camera
                                                               read_only=False)
                for camera_id, config in self.camera_group.camera_configs.items()}

    @property
    def camera_group_configs(self) -> Optional[CameraConfigs]:
        if self.camera_group is None:
            if self.available_cameras is None:
                raise ValueError("Cannot get CameraConfigs without available devices!")
            return available_cameras_to_default_camera_configs(self.available_cameras)
        return self.camera_group.camera_configs

    def set_available_cameras(self, value: AvailableCameras):
        self.available_cameras = value

    def set_device_extracted_camera_config(self, config: CameraConfig):
        if self.camera_group is None or self.camera_group.camera_configs is None:
            raise ValueError("Cannot set device extracted camera config without CameraGroup!")
        self.camera_group.camera_configs[config.camera_id] = config

    def create_camera_group(self, camera_configs: CameraConfigs):
        if self.camera_group is not None:
            self.camera_group.close()
        logger.info(f"Creating camera group with cameras: {camera_configs.keys()}")
        self.camera_group = CameraGroup.create(camera_group_dto=CameraGroupDTO(ipc_queue=self.ipc_queue,
                                                                               ipc_flags=self.ipc_flags,
                                                                               logs_queue=self.logs_queue,
                                                                               update_queue=self.camera_group_update_queue,
                                                                               group_uuid=str(uuid4()),
                                                                               camera_configs=camera_configs),
                                               )
        self.camera_group.start()
        logger.info(f"Camera group created successfully for cameras: {self.camera_group.camera_ids}")

    def update_camera_group(self,
                            camera_configs: CameraConfigs,
                            update_instructions: UpdateInstructions):
        if self.camera_group is None:
            raise ValueError("Cannot update CameraGroup if it does not exist!")
        self.camera_group.update_camera_configs(camera_configs=camera_configs,
                                                update_instructions=update_instructions)

    def close_camera_group(self):
        if self.camera_group is None:
            return
        logger.debug("Closing existing camera group...")
        self.camera_group.close()
        self.shmorchestrator.close_and_unlink()
        self._reset()
        logger.success("Camera group closed successfully")

    def start_recording(self, recording_info:RecordingInfo):
        self.ipc_flags.mic_device_index.value = recording_info.mic_device_index
        self.ipc_flags.record_frames_flag.value = True
        recording_name_string = recording_info.recording_name if recording_info.recording_name else ""
        self.ipc_flags.recording_name.value = recording_name_string.encode("utf-8")

        self.ipc_queue.put(self.state_dto())

    def stop_recording(self):
        self.ipc_flags.record_frames_flag.value = False
        self.ipc_queue.put(self.state_dto())

    def state_dto(self):
        return SkellycamAppStateDTO.from_state(self)

    def _reset(self):
        self.camera_group = None
        self.shmorchestrator = None
        self.ipc_flags = IPCFlags(global_kill_flag=self.ipc_flags.global_kill_flag)

    def shutdown_skellycam(self):
        self.ipc_flags.global_kill_flag.value = True
        if self.camera_group:
            self.close_camera_group()


class SkellycamAppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the SkellycamAppState
    """
    type: str
    state_timestamp: str = datetime.now().isoformat()

    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableCameras]
    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: SkellycamAppState):
        return cls(
            camera_configs=state.camera_group_configs,
            available_devices=state.available_cameras,
            record_frames_flag_status=state.ipc_flags.record_frames_flag.value,
            type=cls.__name__
        )


SKELLYCAM_APP_STATE: Optional[SkellycamAppState] = None


def create_skellycam_app_state(global_kill_flag: multiprocessing.Value,
                               ) -> SkellycamAppState:
    global SKELLYCAM_APP_STATE
    if not SKELLYCAM_APP_STATE:
        SKELLYCAM_APP_STATE = SkellycamAppState.create(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("SkellycamAppState already exists!")
    return SKELLYCAM_APP_STATE


def get_skellycam_app_state() -> SkellycamAppState:
    global SKELLYCAM_APP_STATE
    if SKELLYCAM_APP_STATE is None:
        raise ValueError("SkellycamAppState does not exist!")
    return SKELLYCAM_APP_STATE
