import enum
import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.multiframe_publisher import MultiframeBuilder
from skellycam.core.camera_group.video_manager import VideoManager
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateCameraConfigsMessage, ShmUpdateMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
from skellycam.core.types import CameraIdString, CameraGroupIdString
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraGroupWorkerStrategies(enum.Enum):
    THREAD = "THREAD"
    PROCESS = "PROCESS"


def create_camera_group_id() -> CameraGroupIdString:
    return str(uuid.uuid4())[:6]  # Shortened UUID for readability


@dataclass
class CameraGroup:
    ipc: CameraGroupIPC
    shm: CameraGroupSharedMemoryManager
    cameras: CameraManager
    videos: VideoManager
    mf_builder: MultiframeBuilder

    def id(self) -> CameraGroupIdString:
        return self.ipc.group_id

    @classmethod
    def from_configs(cls, camera_configs: CameraConfigs):

        ipc = CameraGroupIPC.create(camera_configs=camera_configs)
        shm = CameraGroupSharedMemoryManager.create(camera_configs=camera_configs,
                                                    read_only=True)

        return cls(

            ipc=ipc,
            shm=shm,
            cameras=CameraManager.create_cameras(ipc=ipc,
                                                 camera_shm_dtos=shm.to_dto().camera_shm_dtos),
            mf_builder=MultiframeBuilder.create(ipc=ipc,
                                                group_shm_dto=shm.to_dto()),
            videos=VideoManager.create(ipc=ipc,
                                       group_shm_dto=shm.to_dto())
        )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.ipc.camera_configs.keys())

    @property
    def all_ready(self) -> bool:
        return all([self.ipc.all_ready, self.shm.valid])

    def get_latest_multiframe(self, if_newer_than_mf_number: int | None = None) -> MultiFramePayload | None:
        """
        Retrieve the latest multi-frame data if it is newer than the provided multi-frame number.
        """
        if not self.ipc.all_ready:
            return None
        return self.shm.get_latest_multiframe(if_newer_than_mf_number=if_newer_than_mf_number)

    def start(self):
        logger.info("Starting camera group...")
        self.cameras.start()
        self.mf_builder.start()
        self.videos.start()
        while not self.mf_builder.is_alive() and not self.videos.is_alive() and not self.cameras.all_alive and self.ipc.should_continue:
            wait_10ms()
        logger.info(f"Camera group ID: {self.id} sub-processs started -  Awaiting cameras connected...")
        while not self.cameras.cameras_connected and self.ipc.should_continue:
            wait_10ms()
        logger.success(f"Camera group ID: {self.id} started - all cameras connected: {self.camera_ids}!")

    def close(self):
        logger.debug("Closing camera group")

        self.ipc.shutdown_camera_group_flag.value = True
        self.mf_builder.close()
        self.videos.close()
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

    def update_configs(self, new_configs: CameraConfigs) -> CameraConfigs:
        """
        Update the camera configuration for the group.
        """
        if self.ipc.any_recording:
            logger.warning("Cannot update configs while recording.")
        logger.debug("Updating camera configs")
        self.pause(await_paused=True)
        self.ipc.updating_cameras_flag.value = True
        old_configs = deepcopy(self.ipc.camera_configs)
        extracted_configs: dict[CameraIdString, CameraConfig | None] = {camera_id: None for camera_id in new_configs.keys()}
        update_message: UpdateCameraConfigsMessage | None = UpdateCameraConfigsMessage.from_configs(
            old_configs=old_configs,
            new_configs=new_configs,
        )
        extracted_configs_queue = self.ipc.pubsub.topics[TopicTypes.EXTRACTED_CONFIG].get_subscription()
        while self.ipc.updating_cameras_flag.value and not self.ipc.all_ready and self.ipc.should_continue:
            if update_message is not None and update_message.need_update_configs:
                if update_message.need_reset_shm:
                    self._reset_shm(update_message)

                if update_message.need_update_configs:
                    self.ipc.pubsub.topics[TopicTypes.UPDATE_CONFIGS].publish(update_message)
                update_message = None
            if not extracted_configs_queue.empty():
                extracted_config = extracted_configs_queue.get()
                if extracted_config is not None:
                    if extracted_configs[extracted_config.camera_id] is not None:
                        raise ValueError(
                            f"Camera {extracted_config.camera_id} has already been configured. "
                            f"Please check the camera configurations for duplicates."
                        )
                    extracted_configs[extracted_config.camera_id] = extracted_config
                if all(extracted_configs.values()):
                    logger.debug("All camera configs extracted, updating shared memory...")
                    old_configs = deepcopy(new_configs)
                    new_configs = extracted_configs
                    update_message = UpdateCameraConfigsMessage.from_configs(
                        old_configs = old_configs,
                        new_configs = new_configs,
                    )
                    if not update_message.need_update_configs:
                        logger.debug("Camera configs updated successfully.")
                        self.ipc.updating_cameras_flag.value = False
                    else:
                        logger.debug("Extracted configs do not match requested updates - cycling update with extracted configs.")
                        extracted_configs = {camera_id: None for camera_id in new_configs.keys()}
            wait_10ms()
        logger.success("Camera configs updated!")
        return new_configs

    def _reset_shm(self, update_message: UpdateCameraConfigsMessage):
        logger.debug("Resetting shared memory...")
        self.shm.close_and_unlink()
        self.shm = CameraGroupSharedMemoryManager.create(camera_configs=update_message.new_configs,
                                                         read_only=self.shm.read_only)
        self.ipc.camera_orchestrator = CameraOrchestrator.from_configs(
            camera_configs= update_message.new_configs,
        )
        self.ipc.pubsub.topics[TopicTypes.SHM_UPDATES].publish(ShmUpdateMessage(
            group_shm_dto=self.shm.to_dto(),
            orchestrator=self.ipc.camera_orchestrator,
        ))
