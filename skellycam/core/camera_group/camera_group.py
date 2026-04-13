import logging
import multiprocessing
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.camera_worker import CameraState
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig, validate_camera_configs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import (
    DeviceExtractedConfigMessage,
    UpdateCamerasSettingsMessage,
    RecordingInfoMessage,
    RecordingFinishedMessage,
)
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.recording_finalizer import RecordingFinalizer
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.recording_timestamp_stats import RecordingTimestampsStats
from skellycam.core.types.frontend_payload_bytearray import create_frontend_payload
from skellycam.core.types.type_overloads import (
    CameraIdString,
    CameraGroupIdString,
    FrameNumberInt,
    MultiframeTimestampFloat,
)
from skellycam.utilities.wait_functions import await_100ms, await_10ms
from skellycam.core.camera_group.camera_status import CameraStatus

logger = logging.getLogger(__name__)


class CameraGroupState(BaseModel):
    """Serializable representation of a camera group state."""
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True,
    )
    id: CameraGroupIdString
    configs: dict[CameraIdString, CameraConfig]
    cameras: dict[CameraIdString, CameraState]
    alive: bool


@dataclass
class CameraGroup:
    ipc: CameraGroupIPC
    configs: CameraConfigs
    cameras: CameraManager
    shm: CameraGroupSharedMemory | None = None
    started: bool = False
    _audio_recorder: AudioRecorder | None = None

    @property
    def id(self) -> CameraGroupIdString:
        return self.ipc.group_id

    @property
    def alive(self) -> bool:
        return self.cameras.all_ready and all(
            worker.is_alive() for worker in self.cameras.camera_workers.values()
        )

    @classmethod
    def create(
        cls,
        *,
        camera_configs: CameraConfigs,
        heartbeat_timestamp: multiprocessing.Value,
        global_kill_flag: multiprocessing.Value,
        worker_registry: WorkerRegistry,
    ) -> "CameraGroup":
        try:
            validate_camera_configs(camera_configs)
            ipc = CameraGroupIPC.create(
                global_kill_flag=global_kill_flag,
                heartbeat_timestamp=heartbeat_timestamp,
            )

            cameras = CameraManager.create(
                ipc=ipc,
                worker_registry=worker_registry,
                camera_configs=camera_configs,
            )
        except Exception as e:
            logger.error(f"Error creating camera group: {type(e).__name__} - {e}")
            global_kill_flag.value = True
            raise

        return cls(
            ipc=ipc,
            cameras=cameras,
            configs=camera_configs,
        )

    async def start(self) -> CameraConfigs:
        self.started = True
        logger.info(f"Starting camera group ID: {self.id} with cameras: {list(self.configs.keys())}")
        self.cameras.start()
        logger.debug("Awaiting extracted configs so we can create shared memory...")
        extracted_configs: CameraConfigs = await await_extracted_configs(
            ipc=self.ipc, requested_configs=self.configs
        )
        self.shm = CameraGroupSharedMemory.create(
            camera_configs=extracted_configs,
            timebase_mapping=self.ipc.timebase_mapping,
            read_only=True,
        )
        self.ipc.publish_shm_message(shm_dto=self.shm.to_dto())
        self.configs = extracted_configs
        return extracted_configs

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.configs.keys())

    def get_latest_frames(self) -> dict[CameraIdString, np.recarray] | None:
        if self.shm is None or not self.shm.valid:
            return None
        latest_frames = self.shm.get_latest_multiframe()
        if not latest_frames:
            return None
        return latest_frames

    def get_latest_frontend_payload(
        self,
        if_newer_than: int,
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> tuple[FrameNumberInt, MultiframeTimestampFloat, bytes] | None:
        if not self.cameras.all_ready:
            return None
        latest_frames = self.get_latest_frames()
        if not latest_frames:
            return None
        return create_frontend_payload(
            latest_frames=latest_frames,
            display_image_sizes=display_image_sizes,
        )

    def get_frontend_payload_by_frame_number(
        self,
        frame_number: FrameNumberInt,
        display_image_sizes: dict[CameraIdString, dict[str, float]] | None = None,
    ) -> tuple[bytes, MultiframeTimestampFloat] | None:
        if not self.cameras.all_ready:
            return None
        if frame_number > self.shm.latest_multiframe_number:
            return None
        latest_frames = self.shm.get_images_by_frame_number(frame_number=frame_number)
        if not latest_frames:
            return None
        frame_number_out, mf_timestamp, frames_bytearray = create_frontend_payload(
            latest_frames=latest_frames,
            display_image_sizes=display_image_sizes,
        )
        if frame_number_out != frame_number:
            logger.warning(f"Requested frame number {frame_number} but got {frame_number_out}")
        return frames_bytearray, float(mf_timestamp)

    async def pause_unpause(self, await_state_change: bool = True) -> None:
        await self.cameras.pause_unpause(await_state_change)

    async def update_camera_settings(self, requested_configs: CameraConfigs) -> CameraConfigs:
        """Update camera settings and await the extracted configurations."""
        self.ipc.pubsub.topics[TopicTypes.UPDATE_CAMERA_SETTINGS].publish(
            UpdateCamerasSettingsMessage(requested_configs=requested_configs)
        )
        updated_configs = await await_extracted_configs(
            ipc=self.ipc, requested_configs=requested_configs
        )
        self.configs = updated_configs
        logger.info(f"Updated camera configs - {list(requested_configs.keys())}")
        return self.configs

    async def start_recording(self, recording_info: RecordingInfo) -> None:
        """Start recording for the camera group."""
        await self.cameras.pause(await_paused=True)
        logger.info("Publishing recording info message...")
        frame_count = max(
            status.frame_count.value
            for status in self.cameras.orchestrator.camera_statuses.values()
        )
        self.cameras.orchestrator.last_recording_frame_number.value = -1
        self.cameras.orchestrator.first_recording_frame_number.value = frame_count + 3
        self.ipc.pubsub.topics[TopicTypes.RECORDING_INFO].publish(
            RecordingInfoMessage(recording_info=recording_info)
        )

        # Start audio recording if a microphone is selected
        if recording_info.mic_device_index >= 0:
            self._audio_recorder = AudioRecorder(
                audio_file_path=recording_info.audio_file_path,
                mic_device_index=recording_info.mic_device_index,
                timebase_mapping=self.ipc.timebase_mapping,
            )
            self._audio_recorder.start()
            logger.info(f"Audio recording started (mic device {recording_info.mic_device_index})")

        await await_10ms()
        await self.cameras.unpause(await_unpaused=True)
        logger.info("Camera group unpaused - Recording successfully started.")
        logger.info(
            f"Started recording for camera group ID: {self.id} "
            f"with recording name: {recording_info.recording_name}"
        )

    async def stop_recording(self) -> tuple[RecordingInfo, RecordingTimestampsStats]:
        """Stop recording for the camera group."""
        logger.debug("Stopping recording for all cameras in orchestrator...")
        await self.cameras.pause(await_paused=True)

        # Stop audio before finalizing video
        if self._audio_recorder is not None:
            self._audio_recorder.stop()
            logger.info("Audio recording stopped.")
            self._audio_recorder = None

        frame_count = max(
            status.frame_count.value
            for status in self.cameras.orchestrator.camera_statuses.values()
        )
        self.cameras.orchestrator.first_recording_frame_number.value = -1
        self.cameras.orchestrator.last_recording_frame_number.value = frame_count + 3
        await self.cameras.unpause(await_unpaused=True)
        recording_info, timestamp_stats = await finalize_recording(ipc=self.ipc, cameras=self.cameras)
        logger.info(
            f"Stopped recording for camera group ID: {self.id} "
            f"with recording name: {recording_info.recording_name}"
        )
        return recording_info, timestamp_stats

    async def close(self) -> None:
        logger.debug("Closing camera group")

        if any(
            status.recording_in_progress.value
            for status in self.cameras.orchestrator.camera_statuses.values()
        ):
            logger.info("Recording in progress — stopping recording before closing cameras")
            try:
                await self.stop_recording()
            except Exception as e:
                logger.error(f"Error stopping recording during close: {type(e).__name__} - {e}")

        # Stop audio if still running (e.g. error during stop_recording)
        if self._audio_recorder is not None:
            try:
                self._audio_recorder.stop()
            except Exception as e:
                logger.error(f"Error stopping audio during close: {type(e).__name__} - {e}")
            self._audio_recorder = None

        self.ipc.should_continue = False
        self.cameras.close()

        if self.shm is not None:
            try:
                self.shm.unlink_and_close()
            except Exception as e:
                logger.error(f"Error closing shared memory: {type(e).__name__} - {e}")
            logger.success("Shared memory closed and unlinked if applicable.")

        logger.success("Camera group closed successfully.")

    def to_state(self) -> CameraGroupState:
        return CameraGroupState(
            id=self.id,
            configs=self.configs,
            cameras={
                camera_id: worker.to_state()
                for camera_id, worker in self.cameras.camera_workers.items()
            },
            alive=all(
                worker.is_alive() for worker in self.cameras.camera_workers.values()
            ),
        )


async def await_extracted_configs(
    ipc: CameraGroupIPC,
    requested_configs: CameraConfigs,
) -> CameraConfigs:
    updated_configs: dict[CameraIdString, CameraConfig | None] = {
        camera_id: None for camera_id in requested_configs.keys()
    }
    while (
        any(not isinstance(config, CameraConfig) for config in updated_configs.values())
        and ipc.should_continue
    ):
        if not ipc.extracted_config_subscription.empty():
            extracted_config_message = ipc.extracted_config_subscription.get()
            if not isinstance(extracted_config_message, DeviceExtractedConfigMessage):
                raise RuntimeError(
                    f"Received unexpected message type: {type(extracted_config_message)}"
                )
            updated_configs[
                extracted_config_message.extracted_config.camera_id
            ] = extracted_config_message.extracted_config
        await await_100ms()

    validate_camera_configs(updated_configs)

    return updated_configs


async def finalize_recording(
    ipc: CameraGroupIPC,
    cameras: CameraManager,
) -> tuple[RecordingInfo, RecordingTimestampsStats]:
    recording_finished_messages_by_camera: dict[CameraIdString, RecordingFinishedMessage | None] = {
        camera_id: None
        for camera_id in cameras.orchestrator.camera_statuses.keys()
    }
    recording_info: RecordingInfo | None = None

    while (
        any(
            not isinstance(response, RecordingFinishedMessage)
            for response in recording_finished_messages_by_camera.values()
        )
        and ipc.should_continue
    ):
        if not ipc.recording_finished_subscription.empty():
            recording_finished_message = ipc.recording_finished_subscription.get()
            if not isinstance(recording_finished_message, RecordingFinishedMessage):
                raise RuntimeError(
                    f"Received unexpected message type: {type(recording_finished_message)}"
                )

            if recording_finished_messages_by_camera[recording_finished_message.camera_id] is not None:
                raise RuntimeError(
                    f"Received multiple recording finished messages for camera "
                    f"{recording_finished_message.camera_id}."
                )

            logger.debug(
                f"Received recording finished message for camera {recording_finished_message.camera_id}."
            )
            recording_finished_messages_by_camera[recording_finished_message.camera_id] = (
                recording_finished_message
            )
            if recording_info is None:
                recording_info = recording_finished_message.recording_info
            elif recording_info != recording_finished_message.recording_info:
                raise RuntimeError(
                    f"Received multiple recording info messages with different recording names: "
                    f"{recording_info.recording_name} and "
                    f"{recording_finished_message.recording_info.recording_name}"
                )
        await await_100ms()

    if not all(
        isinstance(response, RecordingFinishedMessage)
        for response in recording_finished_messages_by_camera.values()
    ):
        raise RuntimeError("Not all cameras finished recording successfully.")

    recording_finalizer = RecordingFinalizer.create(
        recording_info=recording_info,
        frame_metadatas_by_camera={
            camera_id: message.frame_metadatas
            for camera_id, message in recording_finished_messages_by_camera.items()
        },
    )
    timestamp_stats = await recording_finalizer.finalize_recording()
    return recording_info, timestamp_stats
