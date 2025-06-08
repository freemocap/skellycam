import enum
import logging
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
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateCameraConfigsMessage, UpdateShmMessage, ExtractedConfigMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
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
    mf_builder: MultiframeBuilder

    @property
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
    def all_alive(self):
        return all([self.cameras.all_alive, self.mf_builder.is_alive(), self.videos.is_alive()])

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
        while not self.all_alive and self.ipc.should_continue:
            wait_10ms()
        logger.info(f"Camera group ID: {self.id} sub-processs started -  Awaiting cameras connected...")
        while not self.cameras.cameras_connected and self.ipc.should_continue:
            wait_10ms()
        logger.success(f"Camera group ID: {self.id} started - all cameras connected: {self.camera_ids}!")

    def close(self):
        logger.debug("Closing camera group")

        self.ipc.should_continue = False
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
        logger.debug("Updating camera configs")
        self.pause(await_paused=True)
        self.ipc.updating_cameras_flag.value = True

        self._create_and_send_config_update_message(new_configs=new_configs,
                                                    old_configs=deepcopy(self.ipc.camera_configs))
        extracted_configs: dict[CameraIdString, CameraConfig | None] = {camera_id: None for camera_id in
                                                                        new_configs.keys()}

        while self.ipc.updating_cameras_flag.value and not self.ipc.all_ready and self.ipc.should_continue:

            if not self.ipc.extracted_configs_subscription_queue.empty():

                self._receive_extracted_config_message(extracted_configs)

                if all([isinstance(config, CameraConfig) for config in extracted_configs.values()]):
                    update_message = self._evaluate_extracted_configs(extracted_configs=extracted_configs,
                                                                     requested_update_configs=new_configs)
                    if update_message is None:
                        logger.success("Camera configs updated successfully!")
                    else:
                        logger.warning(
                            "Camera configs were not updated successfully - re-attempting update with extracted configs.")
                        extracted_configs = {camera_id: None for camera_id in new_configs.keys()}
            wait_10ms()
        self.shm.camera_configs = new_configs
        logger.debug("Camera configs update complete!")
        return new_configs

    def _evaluate_extracted_configs(self, extracted_configs: CameraConfigs,
                                   requested_update_configs: CameraConfigs) -> UpdateCameraConfigsMessage | None:
        logger.debug("All camera configs extracted - checking if the matched our request ")

        eval_update_message = UpdateCameraConfigsMessage.from_configs(
            old_configs=requested_update_configs,
            new_configs=extracted_configs
        )
        if not eval_update_message.need_update_configs:
            logger.debug("Camera configs updated successfully.")
            self.ipc.updating_cameras_flag.value = False
            return None
        else:
            logger.debug("Extracted configs do not match requested updates - cycling update with extracted configs.")
            self.ipc.pubsub.topics[TopicTypes.UPDATE_CONFIGS].publish(eval_update_message)
        return eval_update_message

    def _receive_extracted_config_message(self, extracted_configs: CameraConfigs):
        extracted_config_msg = self.ipc.extracted_configs_subscription_queue.get(block=True)
        if not isinstance(extracted_config_msg, ExtractedConfigMessage):
            raise ValueError(f"Expected ExtractedConfigMessage, recieved {type(extracted_config_msg)}")
        if extracted_configs[extracted_config_msg.extracted_config.camera_id] is not None:
            raise ValueError(
                f"Received two copies of camera {extracted_config_msg.extracted_config.camera_id} somehow?")
        extracted_configs[extracted_config_msg.extracted_config.camera_id] = extracted_config_msg.extracted_config

    def _create_and_send_config_update_message(self, new_configs: CameraConfigs, old_configs: CameraConfigs):

        update_message: UpdateCameraConfigsMessage | None = UpdateCameraConfigsMessage.from_configs(
            old_configs=old_configs,
            new_configs=new_configs,
        )
        if update_message.need_update_configs:
            if self.ipc.any_recording and not update_message.only_exposure_changed:
                raise RuntimeError("Cannot update configs while recording.")

            if update_message.need_reset_shm:
                self._handle_shm_update(update_message)
            self.ipc.pubsub.topics[TopicTypes.UPDATE_CONFIGS].publish(update_message)

    def _handle_shm_update(self, configs_update_message: UpdateCameraConfigsMessage):
        logger.debug("Resetting shared memory...")
        self.shm.close_and_unlink()
        self.shm = CameraGroupSharedMemoryManager.create(camera_configs=configs_update_message.new_configs,
                                                         read_only=self.shm.read_only)
        self.ipc.camera_orchestrator = CameraOrchestrator.from_configs(
            camera_configs=configs_update_message.new_configs,
        )
        shm_update_message = UpdateShmMessage(
            group_shm_dto=self.shm.to_dto(),
            orchestrator=self.ipc.camera_orchestrator,
        )
        self.ipc.pubsub.topics[TopicTypes.SHM_UPDATES].publish()
        for camera_to_close in configs_update_message.close_these_cameras:
            self.cameras.close_camera(camera_to_close)
        for new_camera in configs_update_message.new_cameras:
            self.cameras.add_new_camera(
                camera_id=new_camera.camera_id,
                ipc=self.ipc,
                camera_shm_dto=shm_update_message.group_shm_dto.camera_shm_dtos[new_camera.camera_id]
            )
