from typing import Dict, List, Tuple

from skellycam.backend.core.camera.config.camera_config import CameraConfig
from skellycam.backend.core.camera_group.strategies.camera_subarray_pipe_process import (
    CamSubarrayPipeProcess,
)
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload
from skellycam.utilities.array_split_by import dict_split_by

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 1

# https://refactoring.guru/design-patterns/strategy

import logging

logger = logging.getLogger(__name__)


class GroupedProcessStrategy:
    def __init__(
            self,
            camera_configs: Dict[CameraId, CameraConfig],
    ):
        self._camera_configs = camera_configs
        self._processes, self._processes_by_camera_id = self._create_processes()

    def start_capture(self):
        logger.debug(f"Starting camera capture processes...")
        for process in self._processes:
            process.start_capture()

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        for camera_id, process in self._processes_by_camera_id.items():
            new_frames.extend(process.get_new_frames_by_camera_id(camera_id))
        return new_frames

    def _create_processes(
            self, cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ) -> Tuple[List[CamSubarrayPipeProcess], Dict[CameraId, CamSubarrayPipeProcess]]:
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras were provided")

        processes = []
        if _DEFAULT_CAM_PER_PROCESS == 1:
            for camera_id, config in self._camera_configs.items():
                processes.append(
                    CamSubarrayPipeProcess(subarray_camera_configs={camera_id: config})
                )
        else:
            camera_config_subarrays = dict_split_by(
                some_dict=self._camera_configs, split_by=cameras_per_process
            )

            for subarray_configs in camera_config_subarrays:
                logger.debug(f"Creating process for {subarray_configs.keys()}")
                for camera_id in subarray_configs.keys():
                    processes.append(
                        CamSubarrayPipeProcess(
                            subarray_camera_configs=subarray_configs,
                        )
                )

        processes_by_camera_id = {}
        for process in processes:
            for camera_id in process.camera_ids:
                processes_by_camera_id[camera_id] = process

        return processes, processes_by_camera_id

    def update_camera_configs(self, camera_config_dictionary):
        logger.info(f"Updating camera configs: {camera_config_dictionary}")
        for process in self._processes:
            process.update_camera_configs(camera_config_dictionary)
