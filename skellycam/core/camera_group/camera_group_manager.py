import logging
import multiprocessing
from dataclasses import dataclass, field

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, FrameNumberInt
from skellycam.utilities.wait_functions import wait_100ms

logger = logging.getLogger(__name__)

@dataclass
class CameraGroupManager:
    global_kill_flag: multiprocessing.Value
    camera_groups: dict[CameraGroupIdString, CameraGroup] = field(default_factory=dict)
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


    def get_latest_frontend_payloads(self, if_newer_than:int) -> dict[CameraGroupIdString, tuple[FrameNumberInt, bytes]]:
        fe_payloads:dict[CameraGroupIdString, tuple[FrameNumberInt, bytes]] = {}
        if self.closing:
            return fe_payloads
        for camera_group in self.camera_groups.values():
            frame_number, fe_payload =  camera_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
            fe_payloads[camera_group.id] = (frame_number, fe_payload) if fe_payload is not None else None
        return fe_payloads

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