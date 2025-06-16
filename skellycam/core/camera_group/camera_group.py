import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.mf_publisher import MultiframeBuilder
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import DeviceExtractedConfigMessage, UpdateCamerasSettingsMessage, \
    RecordingInfoMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString, WorkerStrategy
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


@dataclass
class CameraGroup:
    ipc: CameraGroupIPC
    configs: CameraConfigs
    cameras: CameraManager
    mf_builder: MultiframeBuilder
    recorder: RecordingManager
    shm: CameraGroupSharedMemoryManager | None = None

    @property
    def id(self) -> CameraGroupIdString:
        return self.ipc.group_id

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               global_kill_flag: multiprocessing.Value,
               group_id: CameraGroupIdString | None = None,
               camera_strategy: WorkerStrategy = WorkerStrategy.THREAD,
               camera_manager_strategy: WorkerStrategy = WorkerStrategy.THREAD,
               recorder_strategy: WorkerStrategy = WorkerStrategy.THREAD,
               mf_builder_strategy: WorkerStrategy = WorkerStrategy.THREAD) -> 'CameraGroup':

        ipc = CameraGroupIPC.create(group_id=group_id,
                                    camera_configs=camera_configs,
                                    global_kill_flag=global_kill_flag)
        recorder = RecordingManager.create(ipc=ipc,
                                           camera_ids=list(camera_configs.keys()),
                                           worker_strategy=recorder_strategy
                                           )
        mf_builder = MultiframeBuilder.create(ipc=ipc,
                                              worker_strategy=mf_builder_strategy)

        # note - create cameras last so others can subscribe to camera updates
        cameras = CameraManager.create(ipc=ipc,
                                       camera_configs=camera_configs,
                                       camera_manager_strategy=camera_manager_strategy,
                                       camera_strategy=camera_strategy,
                                       )

        return cls(
            ipc=ipc,
            cameras=cameras,
            recorder=recorder,
            configs=camera_configs,
            mf_builder=mf_builder,
        )

    def start(self) -> CameraConfigs:
        logger.info(f"Starting camera group ID: {self.id} with cameras: {list(self.configs.keys())}")
        self.cameras.start()
        self.recorder.start()
        self.mf_builder.start()
        logger.debug(f"Awaiting extracted configs so we can create shared memory...")
        extracted_configs: CameraConfigs = await_extracted_configs(ipc=self.ipc, requested_configs=self.configs)
        self.shm = CameraGroupSharedMemoryManager.create(camera_configs=extracted_configs,
                                                    camera_group_id=self.ipc.group_id,
                                                    read_only=True)
        self.ipc.publish_shm_message(shm_dto=self.shm.to_dto())
        return extracted_configs

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.configs.keys())

    @property
    def all_alive(self):
        return all([self.cameras.all_alive, self.recorder.is_alive()])

    @property
    def all_ready(self) -> bool:
        if self.shm is None:
            return False
        return all([self.cameras.all_ready, self.recorder.ready, self.mf_builder.ready,  self.shm.valid])

    def get_latest_frontend_payload(self, if_newer_than: int | None = None) -> FrontendFramePayload | None:
        if self.shm is None:
            return None
        if if_newer_than is not None:
            if self.shm.latest_mf_number.value <= if_newer_than:
                return None
        if not self.shm.latest_multiframe_shm.first_frame_written:
            return None
        mf = self.shm.latest_multiframe_shm.retrieve_multiframe(self.configs)
        if mf is None:
            return None
        return FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf)

    def close(self):
        logger.debug("Closing camera group")

        self.ipc.should_continue = False
        self.recorder.close()
        self.cameras.close()
        self.shm.unlink_and_close()
        logger.info("Camera group closed.")

    def pause(self, await_paused: bool = True):
        """
        Pause the camera group operations.
        """
        logger.info(f"Pausing camera group ID: {self.id}")
        self.cameras.pause(await_paused)

    def unpause(self, await_unpaused: bool = True):
        """
        Unpause the camera group operations.
        """
        logger.info(f"Unpausing camera group ID: {self.id}")
        self.cameras.unpause(await_unpaused)

    def update_camera_settings(self, requested_configs: CameraConfigs) -> CameraConfigs:
        """
        Update camera settings and await the extracted configurations.
        """
        self.ipc.pubsub.topics[TopicTypes.UPDATE_CAMERA_SETTINGS].publish(
            UpdateCamerasSettingsMessage(requested_configs=requested_configs))

        updated_configs = await_extracted_configs(ipc=self.ipc, requested_configs=requested_configs)
        self.configs.update(updated_configs)
        return self.configs

    def start_recording(self, recording_info: RecordingInfo):
        """
        Start recording for the camera group.
        """
        self.ipc.pubsub.topics[TopicTypes.RECORDING_INFO].publish(RecordingInfoMessage(recording_info=recording_info))
        self.recorder.status.should_record.value = True
        logger.info(
            f"Started recording for camera group ID: {self.id} wit recording name: {recording_info.recording_name}")

    def stop_recording(self):
        """
        Stop recording for the camera group.
        """
        self.recorder.status.should_record.value = False
        logger.info(f"Stopped recording for camera group ID: {self.id}")


def await_extracted_configs(ipc: CameraGroupIPC, requested_configs: CameraConfigs) -> CameraConfigs:
    updated_configs: dict[CameraIdString, CameraConfig | None] = {camera_id: None for camera_id in
                                                                  requested_configs.keys()}
    while any([not isinstance(config, CameraConfig) for config in updated_configs.values()]) and ipc.should_continue:
        if not ipc.extracted_config_subscription.empty():
            extracted_config_message = ipc.extracted_config_subscription.get()
            if not isinstance(extracted_config_message, DeviceExtractedConfigMessage):
                raise RuntimeError(f"Received unexpected message type: {type(extracted_config_message)}")
            else:
                updated_configs[
                    extracted_config_message.extracted_config.camera_id] = extracted_config_message.extracted_config
        wait_10ms()
    logger.info(f"Updated camera configs - {list(requested_configs.keys())}")
    return updated_configs
