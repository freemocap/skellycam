import logging
import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString
from skellycam.utilities.wait_functions import wait_100ms

logger = logging.getLogger(__name__)

@dataclass
class CameraGroupManager:
    global_kill_flag: multiprocessing.Value
    camera_groups: dict[CameraGroupIdString, CameraGroup] = field(default_factory=dict)

    @property
    def any_active_camera_groups(self) -> bool:
        """
        Check if there are any active camera groups.
        """
        return self.camera_groups and any(
            [camera_group.running for camera_group in self.camera_groups.values()])

    def create_and_start_camera_group(self, camera_configs:CameraConfigs) -> CameraGroup:
        """
        Create a camera group with the provided configuration settings.
        """
        camera_group = CameraGroup.create(camera_configs = camera_configs,
                                                    global_kill_flag=self.global_kill_flag)
        self.camera_groups[camera_group.id] = camera_group
        self.camera_groups[camera_group.id].start()

        logger.info(f"Creating camera group with ID: {camera_group.id} and cameras: {camera_group.camera_ids}")
        return camera_group

    def get_camera_group(self, camera_group_id: CameraGroupIdString) -> CameraGroup:
        """
        Retrieve a camera group by its ID.
        """
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
        if not self.camera_groups:
            logger.warning("No camera groups to close.")
            return
        for camera_group in self.camera_groups.values():
            camera_group.should_continue = False
        wait_100ms()
        closed_ids:list[CameraIdString] = []
        for camera_group_id in list(self.camera_groups.keys()):
            self.camera_groups[camera_group_id].close()
        logger.success(f"Successfully closed all camera groups ids - {list(self.camera_groups.keys())}")
        self.camera_groups.clear()

    def start_recording_all_groups(self, recording_info:RecordingInfo) -> None:
        """
        Start recording for all camera groups.
        """
        for camera_group in self.camera_groups.values():
            camera_group.start_recording(recording_info=recording_info)
            logger.info(f"Started recording for camera group ID: {camera_group.id}")

    def stop_recording_all_groups(self) -> None:
        """
        Stop recording for all camera groups.
        """
        for camera_group in self.camera_groups.values():
            camera_group.stop_recording()
            logger.info(f"Stopped recording for camera group ID: {camera_group.id}")


    def get_latest_frontend_payloads(self, if_newer_than:int|None) -> list[FrontendFramePayload]:

            fe_payloads = []
            for camera_group in self.camera_groups.values():
                fe_payload =  camera_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if isinstance(fe_payload, FrontendFramePayload):
                    fe_payloads.append(fe_payload)
            return fe_payloads