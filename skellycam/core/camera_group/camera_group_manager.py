import logging
import multiprocessing
from dataclasses import dataclass, field

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager, TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import FramerateMessage
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, FrameNumberInt, \
    MultiframeTimestampFloat, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_100ms

logger = logging.getLogger(__name__)

@dataclass
class CameraGroupManager:
    global_kill_flag: multiprocessing.Value
    camera_groups: dict[CameraGroupIdString, CameraGroup] = field(default_factory=dict)
    camera_group_framerate_subscriptions: dict[CameraGroupIdString, TopicSubscriptionQueue] = field(default_factory=dict)
    closing: bool = False


    def create_and_start_camera_group(self, camera_configs:CameraConfigs) -> CameraGroup| None:
        """
        Create a camera group with the provided configuration settings.
        """
        if self.closing:
            logger.warning("Cannot start recording, camera groups are closing.")
            return None
        camera_group = CameraGroup.create(camera_configs = camera_configs,
                                                    global_kill_flag=self.global_kill_flag)
        self.camera_group_framerate_subscriptions[camera_group.id] = camera_group.ipc.pubsub.get_subscription(TopicTypes.FRAMERATE)
        self.camera_groups[camera_group.id] = camera_group
        self.camera_groups[camera_group.id].start()

        logger.info(f"Creating camera group with ID: {camera_group.id} and cameras: {camera_group.camera_ids}")
        return camera_group

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> CameraGroup|None:
        """
        Retrieve a camera group by its ID.
        """
        if self.closing:
            logger.warning("Cannot start recording, camera groups are closing.")
            return None
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        return self.camera_groups[camera_group_id]

    def _get_configs_by_group(self, camera_configs:CameraConfigs) -> dict[CameraGroupIdString, CameraConfigs]:
        configs_by_group: dict[CameraGroupIdString, CameraConfigs] = {}
        for camera_group in self.camera_groups.values():
            configs_by_group[camera_group.id] = {}
            for camera_id, camera_config in camera_configs.items():
                if camera_id in camera_group.camera_ids:
                    configs_by_group[camera_group.id][camera_id] = camera_config
        return configs_by_group

    def update_camera_settings(self, camera_configs:CameraConfigs) -> CameraConfigs:
        if self.closing:
            logger.warning("Cannot start recording, camera groups are closing.")
            return {}
        extracted_configs: CameraConfigs = {}
        for camera_group_id, camera_configs in self._get_configs_by_group(camera_configs).items():
            extracted_configs.update(self.camera_groups[camera_group_id].update_camera_settings(
                requested_configs=camera_configs))
            logger.info(f"Camera Group ID: {camera_group_id} - Updated Camera Configs for Cameras: {list(camera_configs.keys())}")
        return extracted_configs



    def close_all_camera_groups(self) -> None:
        """
        Close all camera groups.
        """
        self.closing = True
        if not self.camera_groups:
            logger.warning("No camera groups to close.")
            self.closing = False
            return
        for camera_group in self.camera_groups.values():
            camera_group.should_continue = False
        wait_100ms()
        for camera_group_id in list(self.camera_groups.keys()):
            self.camera_groups[camera_group_id].close()
        logger.success(f"Successfully closed all camera groups ids - {list(self.camera_groups.keys())}")
        self.camera_groups.clear()
        self.closing = False

    def start_recording_all_groups(self, recording_info:RecordingInfo) -> None:
        """
        Start recording for all camera groups.
        """
        if self.closing:
            wait_100ms()
        for camera_group in self.camera_groups.values():
            camera_group.start_recording(recording_info=recording_info)
            logger.info(f"Started recording for camera group ID: {camera_group.id}")

    def stop_recording_all_groups(self) -> None:
        """
        Stop recording for all camera groups.
        """
        while self.closing:
            wait_100ms()
        for camera_group in self.camera_groups.values():
            camera_group.stop_recording()
            logger.info(f"Stopped recording for camera group ID: {camera_group.id}")

    def get_new_multiframes(self, if_newer_than: int) -> dict[CameraGroupIdString, np.recarray]:
        """
        Get new multi-frames from all camera groups that are newer than the specified frame number.

        Args:
            if_newer_than: Only return multi-frames with frame numbers greater than this value

        Returns:
            Dictionary mapping camera group IDs to their latest multi-frame record arrays
        """
        multiframes: dict[CameraGroupIdString, np.recarray] = {}

        if self.closing:
            return multiframes

        for camera_group in self.camera_groups.values():
            if camera_group.shm is None or not camera_group.shm.valid:
                continue

            if camera_group.shm.latest_multiframe_number.value <= if_newer_than:
                continue

            mf_rec_array = camera_group.shm.multi_frame_ring_shm.get_latest_multiframe()
            if mf_rec_array is not None:
                multiframes[camera_group.id] = mf_rec_array

        return multiframes
    def get_backend_framerate_updates(self) -> dict[CameraGroupIdString, CurrentFramerate]:
        """
        Get the latest framerate updates for all camera groups.
        """
        if self.closing:
            return {}
        framerate_updates: dict[CameraGroupIdString, CurrentFramerate] = {}
        for camera_group_id, subscription in self.camera_group_framerate_subscriptions.items():
            if not subscription.empty():
                framerate_update = subscription.get()
                if isinstance(framerate_update, FramerateMessage):
                    framerate_updates[camera_group_id] = framerate_update.current_framerate
                else:
                    raise TypeError(f"Received unexpected data type from framerate subscription: {type(framerate_update)}")
        return framerate_updates

    def pause_all_groups(self, await_paused: bool = True) -> None:
        """
        Pause all camera groups.
        """
        if self.closing:
            logger.warning("Cannot pause, camera groups are closing.")
            return
        for camera_group in self.camera_groups.values():
            camera_group.pause(await_paused=await_paused)
            logger.info(f"Paused camera group ID: {camera_group.id}")

    def unpause_all_groups(self, await_unpaused: bool = True) -> None:
        """
        Unpause all camera groups.
        """
        if self.closing:
            logger.warning("Cannot unpause, camera groups are closing.")
            return
        for camera_group in self.camera_groups.values():
            camera_group.unpause(await_unpaused=await_unpaused)
            logger.info(f"Unpaused camera group ID: {camera_group.id}")