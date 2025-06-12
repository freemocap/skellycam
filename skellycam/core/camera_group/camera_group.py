import enum
import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.types import CameraIdString, CameraGroupIdString
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraGroupWorkerStrategies(enum.Enum):
    THREAD = "THREAD"
    PROCESS = "PROCESS"


@dataclass
class CameraGroup:
    ipc: CameraGroupIPC
    shm: CameraGroupSharedMemoryManager
    configs: CameraConfigs
    cameras: CameraManager
    recorder: RecordingManager

    @property
    def id(self) -> CameraGroupIdString:
        return self.ipc.group_id

    @classmethod
    def from_configs(cls, camera_configs: CameraConfigs,
                     global_kill_flag: multiprocessing.Value) -> 'CameraGroup':

        ipc = CameraGroupIPC.create(camera_configs=camera_configs,
                                    global_kill_flag=global_kill_flag)
        shm = CameraGroupSharedMemoryManager.create(camera_configs=camera_configs,
                                                    camera_group_id=ipc.group_id,
                                                    read_only=True)

        return cls(
            ipc=ipc,
            shm=shm,
            cameras=CameraManager.create_cameras(ipc=ipc,
                                                 camera_configs=camera_configs,
                                                 camera_shm_dtos=shm.to_dto().camera_shm_dtos),
            recorder=RecordingManager.create(ipc=ipc,
                                             group_shm_dto=shm.to_dto(),
                                             camera_configs=camera_configs),
            configs=camera_configs
        )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.configs.keys())

    @property
    def all_alive(self):
        return all([self.cameras.all_alive, self.recorder.is_alive()])

    @property
    def all_ready(self) -> bool:
        return all([self.ipc.all_ready, self.shm.valid])

    def get_latest_frontend_payload(self, if_newer_than: int | None = None) -> FrontendFramePayload | None:
        mf = self.shm.get_latest_multiframe(if_newer_than=if_newer_than)
        if mf is None:
            return None
        return FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf)

    def start(self):
        logger.info("Starting camera group...")
        self.cameras.start()
        self.recorder.start()
        while not self.all_alive and self.ipc.should_continue:
            wait_10ms()
        logger.info(f"Camera group ID: {self.id} sub-processs started -  Awaiting cameras connected...")
        while not self.cameras.cameras_connected and self.ipc.should_continue:
            wait_10ms()
        logger.success(f"Camera group ID: {self.id} started - all cameras connected: {self.camera_ids}!")

    def close(self):
        logger.debug("Closing camera group")

        self.ipc.should_continue = False
        self.recorder.close()
        self.cameras.close()
        self.shm.close_and_unlink()
        logger.info("Camera group closed.")

    def pause(self, await_paused: bool = True):
        """
        Pause the camera group operations.
        """
        logger.info(f"Pausing camera group ID: {self.id}")
        self.ipc.pause(await_paused)

    def unpause(self, await_unpaused: bool = True):
        """
        Unpause the camera group operations.
        """
        logger.info(f"Unpausing camera group ID: {self.id}")
        self.ipc.unpause(await_unpaused)


