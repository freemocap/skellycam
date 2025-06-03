import enum
import logging
import uuid
from dataclasses import dataclass, field
from multiprocessing.managers import DictProxy

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.multiframe_publisher import MultiframePublisher
from skellycam.core.camera_group.video_manager import VideoManager
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
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
    cameras: CameraManager
    videos: VideoManager
    mf_publisher: MultiframePublisher
    id: CameraGroupIdString = field(default_factory=lambda: str(uuid.uuid4())[:6])  # Shortened UUID for readability

    @classmethod
    def from_configs(cls, camera_configs: CameraConfigs):
        ipc: CameraGroupIPC = CameraGroupIPC.from_configs(camera_configs=camera_configs)
        shm = CameraGroupSharedMemoryManager.create_from_ipc(camera_group_ipc=ipc,
                                                             read_only=True)

        return cls(
            ipc=ipc,
            shm=shm,
            cameras=CameraManager.create_cameras(ipc=ipc,
                                                 camera_shm_dtos=shm.to_dto().camera_shm_dtos),
            mf_publisher=MultiframePublisher.create(ipc=ipc,
                                                    group_shm_dto=shm.to_dto()),
            videos=VideoManager.create(ipc=ipc,
                                       group_shm_dto=shm.to_dto())
        )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.ipc.camera_configs.keys())

    @property
    def camera_configs(self) -> DictProxy:
        return self.ipc.camera_configs

    def get_latest_multiframe(self, if_newer_than_mf_number: int | None = None) -> MultiFramePayload | None:
        """
        Retrieve the latest multi-frame data if it is newer than the provided multi-frame number.
        """
        if not self.ipc.camera_group_running_flag.value:
            return None
        if not self.shm.valid:
            logger.warning("Shared memory is not valid. Cannot retrieve latest multi-frame.")
            return None
        return self.shm.get_latest_multiframe(if_newer_than_mf_number=if_newer_than_mf_number)

    def start(self):
        logger.info("Starting camera group...")
        self.cameras.start()
        self.mf_publisher.start()
        self.videos.start()
        while not self.mf_publisher.is_alive() and not self.videos.is_alive() and not self.cameras.all_alive and self.ipc.should_continue:
            wait_10ms()
        logger.info(f"Camera group ID: {self.id} sub-processs started -  Awaiting cameras connected...")
        while not self.cameras.cameras_connected and self.ipc.should_continue:
            wait_10ms()
        self.ipc.camera_group_running_flag.value = True
        logger.success(f"Camera group ID: {self.id} started - all cameras connected: {self.camera_ids}!")

    def close_camera(self, camera_id: CameraIdString):
        """
        Close a specific camera by its ID.
        """
        self.cameras.close_camera(camera_id=camera_id)

    def close(self):
        logger.debug("Closing camera group")

        self.ipc.shutdown_camera_group_flag.value = True
        self.ipc.camera_group_running_flag.value = False
        self.mf_publisher.close()
        self.videos.close()
        self.cameras.close()
        self.shm.close_and_unlink()
        logger.info("Camera group closed.")
