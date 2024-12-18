import logging
import multiprocessing
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel

from skellycam.core.recorders.start_recording_request import StartRecordingRequest
from skellycam.skellycam_app.skellycam_app_controller.ipc_flags import IPCFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import CameraGroupSharedMemoryOrchestrator
from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFrameRate
from skellycam.system.device_detection.camera_device_info import AvailableCameras, \
    available_cameras_to_default_camera_configs

logger = logging.getLogger(__name__)


@dataclass
class SkellycamAppState:
    ipc_flags: IPCFlags
    ipc_queue: multiprocessing.Queue
    config_update_queue: multiprocessing.Queue

    shmorchestrator: Optional[CameraGroupSharedMemoryOrchestrator] = None
    camera_group_dto: Optional[CameraGroupDTO] = None
    camera_group: Optional[CameraGroup] = None
    available_cameras: Optional[AvailableCameras] = None
    current_framerate: Optional[CurrentFrameRate] = None

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls(ipc_flags=IPCFlags(global_kill_flag=global_kill_flag),
                   ipc_queue=multiprocessing.Queue(),
                   config_update_queue=multiprocessing.Queue())


    @property
    def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer:
        return self.shmorchestrator.multi_frame_escape_ring_shm

    @property
    def camera_group_configs(self) -> Optional[CameraConfigs]:
        if self.camera_group is None:
            if self.available_cameras is None:
                raise ValueError("Cannot get CameraConfigs without available devices!")
            return available_cameras_to_default_camera_configs(self.available_cameras)
        return self.camera_group.camera_configs

    def set_available_cameras(self, value: AvailableCameras):
        self.available_cameras = value
        self.ipc_queue.put(self.state_dto())

    def create_camera_group(self, camera_configs: CameraConfigs):
        if camera_configs is None:
            raise ValueError("Cannot create CameraGroup without camera_configs!")
        # if self.available_devices is None:
        #     raise ValueError("Cannot get CameraConfigs without available devices!")
        self.camera_group_dto = CameraGroupDTO(camera_configs=camera_configs,
                                               ipc_queue=self.ipc_queue,
                                               ipc_flags=self.ipc_flags,
                                               config_update_queue=self.config_update_queue,
                                               group_uuid=str(uuid4())
                                               )
        self.shmorchestrator = CameraGroupSharedMemoryOrchestrator.create(camera_group_dto=self.camera_group_dto,
                                                                          ipc_flags=self.ipc_flags,
                                                                          read_only=True)
        self.camera_group = CameraGroup.create(camera_group_dto=self.camera_group_dto,
                                               shmorc_dto=self.shmorchestrator.to_dto()
                                               )

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
            logger.warning("Camera group does not exist, so it cannot be closed!")
            return
        logger.debug("Closing existing camera group...")
        self.camera_group.close()
        self.shmorchestrator.close_and_unlink()
        self._reset()
        logger.success("Camera group closed successfully")

    def start_recording(self, request: StartRecordingRequest):
        self.ipc_flags.mic_device_index.value = request.mic_device_index
        self.ipc_flags.record_frames_flag.value = True
        self.ipc_queue.put(self.state_dto())

    def stop_recording(self):
        self.ipc_flags.record_frames_flag.value = False
        self.ipc_queue.put(self.state_dto())

    def state_dto(self):
        return SkellycamAppStateDTO.from_state(self)

    def _reset(self):
        self.camera_group = None
        self.shmorchestrator = None
        self.current_framerate = None
        self.ipc_flags = IPCFlags(global_kill_flag=self.ipc_flags.global_kill_flag)


class SkellycamAppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the SkellycamAppState
    """
    type: str = "SkellycamAppStateDTO"
    state_timestamp: str = datetime.now().isoformat()

    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableCameras]
    current_framerate: Optional[CurrentFrameRate]
    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: SkellycamAppState):
        return cls(
            camera_configs=state.camera_group_configs,
            available_devices=state.available_cameras,
            current_framerate=state.current_framerate,
            record_frames_flag_status=state.ipc_flags.record_frames_flag.value,
        )
