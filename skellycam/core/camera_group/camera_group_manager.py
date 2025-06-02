import logging
from dataclasses import dataclass, field

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraGroupIdString, CameraIdString

logger = logging.getLogger(__name__)

@dataclass
class CameraGroupManager:
    camera_groups: dict[CameraGroupIdString, CameraGroup] = field(default_factory=dict)

    def create_camera_group(self, camera_configs:CameraConfigs) -> CameraGroupIdString:
        """
        Create a camera group with the provided configuration settings.
        """
        camera_group = CameraGroup.from_configs(camera_configs = camera_configs)
        self.camera_groups[camera_group.id] = camera_group

        logger.info(f"Creating camera group with ID: {camera_group.id} and cameras: {camera_group.camera_ids}")
        return camera_group.id

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> CameraGroup:
        """
        Retrieve a camera group by its ID.
        """
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        return self.camera_groups[camera_group_id]

    def update_camera_config(self, camera_config:CameraConfig):
        for camera_group in self.camera_groups.values():
            if camera_config.camera_id in camera_group.camera_configs:
                camera_group.ipc.set_config_by_id(camera_id=camera_config.camera_id,
                                                    camera_config=camera_config)
                logger.info(f"Updated camera config for camera ID: {camera_config.camera_id} in group ID: {camera_group.id}")

    def close_camera_group(self, camera_group_id: CameraGroupIdString) -> None:
        """
        Remove a camera group by its ID.
        """
        if camera_group_id not in self.camera_groups:
            raise ValueError(f"Camera group with ID {camera_group_id} does not exist.")
        camera_group = self.camera_groups.pop(camera_group_id)
        camera_group.close()
        logger.info(f"Closed camera group with ID: {camera_group_id}")

    def close_all_camera_groups(self) -> None:
        """
        Close all camera groups.
        """
        for camera_group_id in list(self.camera_groups.keys()):
            self.close_camera_group(camera_group_id)
        logger.info("Closed all camera groups.")

    def close_camera(self, camera_id: CameraIdString) -> None:
        """
        Close a specific camera by its ID across all camera groups.
        """
        for camera_group in self.camera_groups.values():
            if camera_id in camera_group.camera_ids:
                camera_group.close_camera(camera_id=camera_id)

    def start_recording_all_groups(self, recording_info:RecordingInfo) -> None:
        """
        Start recording for all camera groups.
        """
        for camera_group in self.camera_groups.values():
            camera_group.ipc.start_recording(recording_info=recording_info)
            logger.info(f"Started recording for camera group ID: {camera_group.id}")

    def stop_recording_all_groups(self) -> None:
        """
        Stop recording for all camera groups.
        """
        for camera_group in self.camera_groups.values():
            camera_group.ipc.stop_recording()
            logger.info(f"Stopped recording for camera group ID: {camera_group.id}")

    def get_all_latest_multiframes(self, if_newer_than_mf_number: int|None=None) -> dict[CameraGroupIdString, MultiFramePayload]:
        """
        Retrieve the latest multi-frames from all camera groups.
        """
        latest_multiframe_by_camera_group = {}
        for camera_group in self.camera_groups.values():
            latest_multiframe_by_camera_group[camera_group.id] = camera_group.get_latest_multiframe(if_newer_than_mf_number=if_newer_than_mf_number)
        return latest_multiframe_by_camera_group