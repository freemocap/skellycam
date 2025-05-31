import enum
import logging
import uuid
from dataclasses import dataclass, field
from multiprocessing.managers import DictProxy

from skellycam import MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.orchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler
from skellycam.core.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.types import CameraIdString, CameraGroupIdString

logger = logging.getLogger(__name__)


class CameraGroupWorkerStrategies(enum.Enum):
    THREAD = "THREAD"
    PROCESS = "PROCESS"


@dataclass
class CameraGroup:
    ipc: CameraGroupIPC
    camera_shm: CameraGroupSharedMemory
    multiframe_shm: MultiFrameEscapeSharedMemoryRingBuffer
    cameras: CameraManager
    orchestrator: CameraGroupOrchestrator
    frame_wrangler: FrameWrangler
    id: CameraGroupIdString = field(default_factory=lambda: uuid.uuid4()[:6])  # Shortened UUID for readability

    @classmethod
    def from_configs(cls, camera_configs: CameraConfigs):
        ipc: CameraGroupIPC = CameraGroupIPC.from_configs(camera_configs=camera_configs)
        camera_shm = CameraGroupSharedMemory.from_ipc(camera_group_ipc=ipc,
                                               read_only=True)
        multiframe_shm = MultiFrameEscapeSharedMemoryRingBuffer.create_from_ipc(ipc=ipc,
                                                                                read_only=True)

        orchestrator = CameraGroupOrchestrator.from_camera_ids(ipc.camera_ids)
        cameras = CameraManager.create_cameras(ipc=ipc,
                                               camera_shm=camera_shm,
                                               orchestrator=orchestrator)
        frame_wrangler = FrameWrangler.from_ipc(ipc=ipc,
                                                multi_frame_shm_dto=multiframe_shm.to_dto(),
                                                )
        return cls(
            ipc=ipc,
            camera_shm=camera_shm,
            multiframe_shm=multiframe_shm,
            cameras=cameras,
            orchestrator=orchestrator,
            frame_wrangler=frame_wrangler,
        )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.ipc.camera_configs.keys())

    @property
    def camera_configs(self) -> DictProxy:
        return self.ipc.camera_configs

    def start(self):
        logger.info("Starting camera group...")
        self.frame_wrangler.start()
        self.orchestrator.start()

    def close(self):
        logger.debug("Closing camera group")
        self.ipc.should_close_camera_group_flag.value = True
        self.cameras.close()
        self.frame_wrangler.close()
        self.shm.close_and_unlink()
        logger.info("Camera group closed.")
