import logging
import multiprocessing
from typing import Dict, List

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.cam_group_process import CamGroupProcess
from skellycam.opencv.group.strategies.shared_camera_memory_manager import SharedCameraMemoryManager
from skellycam.utils.array_split_by import array_split_by

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

logger = logging.getLogger(__name__)


class GroupedProcessStrategy:
    def __init__(self, camera_ids: List[str]):
        self._camera_ids = camera_ids

        self._create_shared_memory_objects()
        self._processes, self._cam_id_process_map = self._create_processes(self._camera_ids)

    @property
    def processes(self):
        return self._processes

    @property
    def is_capturing(self):
        for process in self._processes:
            if not process.is_capturing:
                return False
        return True

    @property
    def frame_lists_by_camera(self) -> Dict[str, List[FramePayload]]:
        return self._frame_lists_by_camera

    @property
    def video_save_paths_by_camera(self) -> Dict[str, str]:
        return self._video_save_paths_by_camera

    @property
    def recording_frames(self) -> multiprocessing.Value:
        return self._recording_frames

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        return self._latest_frames

    def check_if_camera_is_ready(self, cam_id: str) -> bool:
        for process in self._processes:
            if cam_id in process.camera_ids:
                return process.check_if_camera_is_ready(cam_id)

    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
    ):
        for process in self._processes:
            process.start_capture(
                event_dictionary=event_dictionary,
                camera_config_dict=self._incoming_camera_configs
            )

    def _create_processes(
            self, camera_ids: List[str], cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ):
        if len(camera_ids) == 0:
            raise ValueError("No cameras were provided")
        camera_subarrays = array_split_by(camera_ids, cameras_per_process)
        processes = [
            CamGroupProcess(camera_ids=cam_id_subarray,
                            latest_frames=self._latest_frames,
                            frame_lists_by_camera=self._frame_lists_by_camera,
                            incoming_camera_configs=self._incoming_camera_configs,
                            recording_frames=self._recording_frames,
                            ) for cam_id_subarray in camera_subarrays
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

    def _create_shared_memory_objects(self):
        self._shared_memory_manager = SharedCameraMemoryManager()
        self._latest_frames = self._shared_memory_manager.create_dictionary(keys=self._camera_ids)
        self._frame_lists_by_camera = self._shared_memory_manager.create_dictionary_of_lists(keys=self._camera_ids)
        self._video_save_paths_by_camera = self._shared_memory_manager.create_dictionary_of_strings(keys=self._camera_ids)
        self._recording_frames = self._shared_memory_manager.create_value(type='b', initial_value=False)

        self._incoming_camera_configs = self._shared_memory_manager.create_dictionary(keys=self._camera_ids)

        for camera_id in self._camera_ids:
            self._incoming_camera_configs[camera_id] = CameraConfig(camera_id=camera_id)
