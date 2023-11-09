import multiprocessing
from typing import Dict, List, Tuple

from skellycam.backend.controller.core_functionality.camera_group.strategies.camera_subarray_pipe_process import \
    CamSubarrayPipeProcess
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload
from skellycam.utilities.array_split_by import dict_split_by

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

from skellycam.system.environment.get_logger import logger


class GroupedProcessStrategy:
    def __init__(self,
                 camera_configs: Dict[CameraId, CameraConfig],
                 is_capturing_events_by_camera: Dict[CameraId, multiprocessing.Event],
                 close_cameras_event: multiprocessing.Event,
                 all_cameras_ready_event: multiprocessing.Event, ):
        self._camera_configs = camera_configs
        self._is_capturing_events_by_camera = is_capturing_events_by_camera
        self._close_cameras_event = close_cameras_event
        self._all_cameras_ready_event = all_cameras_ready_event
        self._processes, self._processes_by_camera_id = self._create_processes()

    def start_capture(self):
        for process in self._processes:
            process.start_capture()

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        for camera_id, process in self._processes_by_camera_id.items():
            new_frames.extend(process.get_new_frames_by_camera_id(camera_id))
        return new_frames

    def _create_processes(
            self,
            cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ) -> Tuple[List[CamSubarrayPipeProcess], Dict[CameraId, CamSubarrayPipeProcess]]:

        if len(self._camera_configs) == 0:
            raise ValueError("No cameras were provided")
        camera_config_subarrays = dict_split_by(some_dict=self._camera_configs,
                                                split_by=cameras_per_process)

        processes = []
        for subarray_configs in camera_config_subarrays:
            logger.debug(f"Creating process for {subarray_configs.keys()}")
            is_capturing_events_by_subarray = {}
            for camera_id in subarray_configs.keys():
                is_capturing_events_by_subarray[camera_id] = self._is_capturing_events_by_camera[camera_id]
            processes.append(CamSubarrayPipeProcess(subarray_camera_configs=subarray_configs,
                                                    all_cameras_ready_event=self._all_cameras_ready_event,
                                                    close_cameras_event=self._close_cameras_event,
                                                    is_capturing_events_by_subarray_cameras=is_capturing_events_by_subarray,
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
