import multiprocessing
from typing import Dict, List

from skellycam.backend.controller.core_functionality.camera_group.strategies.cam_group_pipe_process import \
    CamGroupPipeProcess
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload
from skellycam.utilities.array_split_by import dict_split_by

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

from skellycam import logger


class GroupedProcessStrategy:
    def __init__(self, camera_configs: Dict[CameraId, CameraConfig]):
        self._camera_configs = camera_configs
        self._processes, self._cam_id_process_map = self._create_processes()

    @property
    def processes(self):
        return self._processes

    @property
    def is_capturing(self):
        for process in self._processes:
            if not process.is_capturing:
                return False
        return True


    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
    ):

        for process in self._processes:
            process.start_capture(event_dictionary=event_dictionary)

    def check_if_camera_is_ready(self, cam_id: str) -> bool:
        for process in self._processes:
            if cam_id in process.camera_ids:
                return process.check_if_camera_is_ready(cam_id)

    def get_current_frame_by_cam_id(self, camera_id: str):
        for process in self._processes:
            current_frame = process.get_current_frame_by_camera_id(camera_id)
            if current_frame:
                return current_frame


    def get_latest_frames(self) -> Dict[str, FramePayload]:
        return {
            cam_id: process.get_current_frame_by_camera_id(cam_id)
            for cam_id, process in self._cam_id_process_map.items()
        }

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        for camera_id, process in self._cam_id_process_map.items():
            new_frames.extend(process.get_new_frames_by_camera_id(camera_id))
        return new_frames

    def _create_processes(
            self,
            cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ):
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras were provided")
        camera_subarrays = dict_split_by(self._camera_configs, cameras_per_process)
        processes = [
            CamGroupPipeProcess(camera_subarray) for camera_subarray in camera_subarrays
        ]
        cam_id_to_process = {}
        for process in processes:
            for cam_id in process.camera_ids:
                cam_id_to_process[cam_id] = process
        return processes, cam_id_to_process

    def update_camera_configs(self, camera_config_dictionary):
        logger.info(f"Updating camera configs: {camera_config_dictionary}")
        for process in self._processes:
            process.update_camera_configs(camera_config_dictionary)
