import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig, validate_camera_configs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.mf_builder import MultiframeBuilder
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.frame_payloads.multiframes.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import DeviceExtractedConfigMessage, UpdateCamerasSettingsMessage, \
    RecordingInfoMessage, RecordingFinishedMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
from skellycam.core.recorders.videos.recording_finalizer import RecordingFinalizer
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import create_frontend_payload_from_mf_recarray
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString, WorkerStrategy, FrameNumberInt
from skellycam.utilities.wait_functions import wait_10ms, wait_1s, wait_30ms

logger = logging.getLogger(__name__)


@dataclass
class CameraGroup:
    ipc: CameraGroupIPC
    configs: CameraConfigs
    cameras: CameraManager
    mf_builder: MultiframeBuilder
    # recorder: RecordingManager
    shm: CameraGroupSharedMemoryManager | None = None
    mf: MultiFramePayload | None = None  # Local copy of the latest multi-frame payload

    @property
    def id(self) -> CameraGroupIdString:
        return self.ipc.group_id

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               global_kill_flag: multiprocessing.Value,
               group_id: CameraGroupIdString | None = None,
               camera_strategy: WorkerStrategy = WorkerStrategy.PROCESS,

               # recorder_strategy: WorkerStrategy = WorkerStrategy.PROCESS,
               mf_builder_strategy: WorkerStrategy = WorkerStrategy.PROCESS) -> 'CameraGroup':

        ipc = CameraGroupIPC.create(group_id=group_id,
                                    camera_configs=camera_configs,
                                    global_kill_flag=global_kill_flag)
        # recorder = RecordingManager.create(ipc=ipc,
        #                                    worker_strategy=recorder_strategy
        #                                    )
        mf_builder = MultiframeBuilder.create(ipc=ipc,
                                              worker_strategy=mf_builder_strategy)

        # note - create cameras last so others can subscribe to camera updates
        cameras = CameraManager.create(ipc=ipc,
                                       camera_configs=camera_configs,
                                       camera_strategy=camera_strategy,
                                       )

        return cls(
            ipc=ipc,
            cameras=cameras,
            # recorder=recorder,
            configs=camera_configs,
            mf_builder=mf_builder,
        )

    def start(self) -> CameraConfigs:
        logger.info(f"Starting camera group ID: {self.id} with cameras: {list(self.configs.keys())}")
        self.cameras.start()
        # self.recorder.start()
        self.mf_builder.start()
        logger.debug(f"Awaiting extracted configs so we can create shared memory...")
        extracted_configs: CameraConfigs = await_extracted_configs(ipc=self.ipc, requested_configs=self.configs)
        self.shm = CameraGroupSharedMemoryManager.create(camera_configs=extracted_configs,
                                                         timebase_mapping=self.ipc.timebase_mapping,
                                                         read_only=True)
        self.ipc.publish_shm_message(shm_dto=self.shm.to_dto())
        self.configs = extracted_configs
        return extracted_configs

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.configs.keys())

    @property
    def all_alive(self):
        return all([self.cameras.all_alive,
                    # self.recorder.is_alive(),
                    self.mf_builder.is_alive()])

    @property
    def any_alive(self):
        return any([self.cameras.any_alive,
                    # self.recorder.is_alive(),
                    self.mf_builder.is_alive()])

    @property
    def all_ready(self) -> bool:
        if self.shm is None:
            return False
        return all([self.cameras.all_ready,
                    # self.recorder.ready,
                    self.mf_builder.ready,
                    self.shm.valid])

    def get_latest_frontend_payload(self, if_newer_than: int) -> tuple[FrameNumberInt, bytes] | None:
        if self.shm is None or not self.shm.valid:
            return None
        if self.shm.latest_multiframe_number.value <= if_newer_than:
            return None

        mf_rec_array = self.shm.multi_frame_ring_shm.get_latest_multiframe()
        if mf_rec_array is None:
            return None
        return create_frontend_payload_from_mf_recarray(
            mf_rec_array=mf_rec_array,
        )

    def pause(self, await_paused: bool = True):
        """
        Pause the camera group operations.
        """
        logger.info(f"Pausing camera group ID: {self.id}")
        self.ipc.pause(await_paused=await_paused)
        logger.info(f"Camera group ID: {self.id} is paused.")

    def unpause(self, await_unpaused: bool = True):
        """
        Unpause the camera group operations.
        """
        logger.info(f"Unpausing camera group ID: {self.id}")
        self.ipc.unpause(await_unpaused)
        logger.info(f"Camera group ID: {self.id} is unpaused.")

    def update_camera_settings(self, requested_configs: CameraConfigs) -> CameraConfigs:
        """
        Update camera settings and await the extracted configurations.
        """
        self.ipc.pubsub.topics[TopicTypes.UPDATE_CAMERA_SETTINGS].publish(
            UpdateCamerasSettingsMessage(requested_configs=requested_configs))

        updated_configs = await_extracted_configs(ipc=self.ipc, requested_configs=requested_configs)
        self.configs = updated_configs
        logger.info(f"Updated camera configs - {list(requested_configs.keys())}")
        return self.configs

    def start_recording(self, recording_info: RecordingInfo):
        """
        Start recording for the camera group.
        """
        self.ipc.pause(await_paused=True)
        logger.info("Publishing recording info message...")
        self.ipc.pubsub.topics[TopicTypes.RECORDING_INFO].publish(RecordingInfoMessage(recording_info=recording_info))
        while not self.ipc.all_ready_to_record and self.ipc.should_continue:
            wait_10ms()
        logger.api(f"All cameras are ready to record for camera group ID: {self.id}")
        self.ipc.should_record.value = True
        wait_10ms()
        logger.api("Unpausing camera group to start recording...")
        self.ipc.unpause(await_unpaused=True)
        logger.info("Camera group unpaused - Recording successfully started.")

        logger.info(
            f"Started recording for camera group ID: {self.id} wit recording name: {recording_info.recording_name}")

    def stop_recording(self):
        """
        Stop recording for the camera group.
        """

        logger.debug(f"Stopping recording for all cameras in orchestrator...")
        self.pause(await_paused=True)
        self.ipc.should_record.value = False
        self.unpause(await_unpaused=True)
        finalize_recording(ipc=self.ipc)
        logger.info(f"Stopped recording for camera group ID: {self.id}")

    def close(self):
        logger.debug("Closing camera group")
        self.ipc.pause(await_paused=True)
        self.ipc.should_continue = False
        wait_1s()
        self.mf_builder.close()

        while self.any_alive:
            logger.debug(
                f"Waiting for all camera group processes to close, cameras: {self.cameras.any_alive}, mf_builder: {self.mf_builder.is_alive()}")
            wait_1s()

        if self.shm is not None:
            try:
                self.shm.unlink_and_close()
            except Exception as e:
                logger.error(f"Error closing shared memory: {type(e).__name__} - {e}")

            logger.success("Shared memory closed and unlinked if applicable.")

        logger.success("Camera group closed successfully.")


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
    validate_camera_configs(updated_configs)

    return updated_configs


def finalize_recording(ipc: CameraGroupIPC):
    recording_finished_messages_by_camera: dict[CameraIdString, RecordingFinishedMessage | None] = {camera_id: None for camera_id in
                                                                                   ipc.camera_ids}
    recording_info: RecordingInfo | None = None
    while any([not isinstance(response, RecordingFinishedMessage) for response in
               recording_finished_messages_by_camera.values()]) and ipc.should_continue:
        if not ipc.recording_finished_subscription.empty():
            recording_finished_message = ipc.recording_finished_subscription.get()
            if not isinstance(recording_finished_message, RecordingFinishedMessage):
                raise RuntimeError(f"Received unexpected message type: {type(recording_finished_message)}")

            if recording_finished_messages_by_camera[recording_finished_message.camera_id] is not None:
                raise RuntimeError(
                    f"Received multiple recording finished messages for camera {recording_finished_message.camera_id}.")

            logger.debug(f"Recieved recording finished message for camera {recording_finished_message.camera_id}.")
            recording_finished_messages_by_camera[recording_finished_message.camera_id] = recording_finished_message
            if recording_info is None:
                recording_info = recording_finished_message.recording_info
            elif recording_info != recording_finished_message.recording_info:
                raise RuntimeError(
                    f"Received multiple recording info messages with different recording names: "
                    f"{recording_info.recording_name} and {recording_finished_message.recording_info.recording_name}")
        wait_30ms()

    recording_finalizer = RecordingFinalizer.create(
        recording_info=recording_info,
        frame_metadatas_by_camera={camera_id: message.frame_metadatas for camera_id, message in recording_finished_messages_by_camera.items() if message is not None},
    )
    recording_finalizer.finalize_recording()
    logger.success(f"Recording finalized for recording name: {recording_info.recording_name}.")
