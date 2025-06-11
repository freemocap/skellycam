import enum
import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.multiframe_publisher import MultiframeBuilder
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import  UpdateShmMessage, \
    ExtractedConfigMessage, UpdateCameraSettingsMessage
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
    cameras: CameraManager
    recorder: RecordingManager
    mf_builder: MultiframeBuilder

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
            cameras=CameraManager.create_cameras(ipc=ipc, camera_shm_dtos=shm.to_dto().camera_shm_dtos),
            recorder=RecordingManager.create(ipc=ipc, group_shm_dto=shm.to_dto()),
            mf_builder=MultiframeBuilder.create(ipc=ipc, group_shm_dto=shm.to_dto()),

        )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.ipc.camera_configs.keys())

    @property
    def all_alive(self):
        return all([self.cameras.all_alive, self.mf_builder.is_alive(), self.recorder.is_alive()])

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
        self.mf_builder.start()
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
        self.mf_builder.close()
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

    def update_camera_settings(self, desired_configs: CameraConfigs) -> CameraConfigs:
        """
        Update the camera configuration for the group.
        """

        logger.debug("Updating camera configs")
        update_settings_message = UpdateCameraSettingsMessage.from_configs(
            current_configs=self.ipc.camera_configs,
            desired_configs=desired_configs,
        )

        if not update_settings_message.need_update_configs:
            logger.debug("No camera configs update needed - returning current configs.")
            return self.ipc.camera_configs

        if self.ipc.any_recording and not update_settings_message.only_exposure_changed:
            logger.error("Cannot update configs while recording. Please stop recording first.")
            return self.ipc.camera_configs

        self.ipc.updating_cameras_flag.value = True

        if update_settings_message.need_reset_shm:
            logger.debug("Camera configs update requires resetting shared memory.")
            self.pause(await_paused=True)



        self.ipc.camera_configs.update(desired_configs)

        extracted_configs: dict[CameraIdString, CameraConfig | None] = {camera_id: None for camera_id in
                                                                        desired_configs.keys()}

        while self.ipc.should_continue and any([not isinstance(config, CameraConfig) for config in extracted_configs.values()]):
            if not self.ipc.extracted_configs_subscription_queue.empty():
                self._receive_extracted_config_message(extracted_configs)


        if update_settings_message.need_reset_shm:
            self.shm.close_and_unlink()
            self.shm = CameraGroupSharedMemoryManager.create(camera_configs=update_settings_message.desired_configs,
                                                             camera_group_id=self.ipc.group_id,
                                                             read_only=self.shm.read_only)
            if update_settings_message.cameras_to_remove or update_settings_message.cameras_to_add:
                self._remove_cameras(update_settings_message.cameras_to_remove)
                self._add_cameras(update_settings_message.cameras_to_add)
            shm_update_message = UpdateShmMessage(group_shm_dto=self.shm.to_dto(),
                                                  orchestrator=self.ipc.camera_orchestrator)
            self.ipc.pubsub.topics[TopicTypes.SHM_UPDATES].publish(shm_update_message)
            wait_10ms()

        self.ipc.unpause(await_unpaused=True)
        logger.debug("Camera configs update complete!")
        return desired_configs

    def _receive_extracted_config_message(self, extracted_configs: CameraConfigs):
        extracted_config_msg = self.ipc.extracted_configs_subscription_queue.get(block=True)
        if not isinstance(extracted_config_msg, ExtractedConfigMessage):
            raise ValueError(f"Expected ExtractedConfigMessage, recieved {type(extracted_config_msg)}")
        if extracted_configs[extracted_config_msg.extracted_config.camera_id] is not None:
            raise ValueError(
                f"Received two copies of camera {extracted_config_msg.extracted_config.camera_id} somehow?")
        if not extracted_config_msg.extracted_config.camera_id in extracted_configs:
            raise ValueError(
                f"Received camera config for {extracted_config_msg.extracted_config.camera_id} "
                f"which was not requested in the update: {list(extracted_configs.keys())}")
        extracted_configs[extracted_config_msg.extracted_config.camera_id] = extracted_config_msg.extracted_config


    def _remove_cameras(self, cameras_to_remove: list[CameraIdString]):
        for camera_id in cameras_to_remove:
            logger.debug(f"Removing camera {camera_id} from camera group {self.id}")
            self.cameras.remove_camera(camera_id)
            self.ipc.remove_camera(camera_id)


    def _add_cameras(self, cameras_to_add:list[CameraConfig]):
        for camera_config in cameras_to_add:
            logger.debug(f"Adding camera {camera_config.camera_id} to camera group {self.id}")
            self.cameras.add_new_camera(camera_id=camera_config.camera_id,
                                        ipc=self.ipc,
                                        camera_shm_dto=self.shm.to_dto().camera_shm_dtos[camera_config.camera_id],
                                        )
            self.ipc.add_camera(camera_config)


