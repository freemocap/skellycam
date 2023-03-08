import logging
import multiprocessing
from pathlib import Path
from typing import Dict, List, Union

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.cam_group_process import CamGroupProcess
from skellycam.opencv.group.strategies.shared_camera_memory_manager import SharedCameraMemoryManager

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

logger = logging.getLogger(__name__)


class GroupedProcessStrategy:
    def __init__(self,
                 camera_ids: List[str],
                 camera_configs: Dict[str, CameraConfig]):
        self._camera_ids = camera_ids

        self._create_shared_memory_objects()
        self._processes, self._cam_id_process_map = self._create_processes(camera_ids = self._camera_ids,
                                                                           camera_configs= camera_configs)

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
    def folder_to_save_videos(self) -> List[str]:
        return self._folder_to_save_videos

    @folder_to_save_videos.setter
    def folder_to_save_videos(self, path: Union[str, Path]):
        if len(self._folder_to_save_videos) == 0:
            self._folder_to_save_videos.append(str(path))
        else:
            raise Exception("Folder to save videos already set!")

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        try:
            return {camera_id: (self._frame_lists_by_camera[camera_id][-1]) for camera_id in self._camera_ids}
        except:
            return {camera_id: None for camera_id in self._camera_ids}

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
            )

    def _create_processes(
            self,
            camera_ids: List[str],
            camera_configs: Dict[str, CameraConfig],
            cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ):
        if len(camera_ids) == 0:
            raise ValueError("No cameras were provided")
        # camera_group_subarrays = array_split_by(camera_ids, cameras_per_process)

        camera_group_subarrays: list[list[str]] = []
        for camera_number in range(0, len(camera_ids)):
            if camera_number % cameras_per_process == 0:
                sub_array_list: list[str] = []
                camera_group_subarrays.append(sub_array_list)
            sub_array_list.append(str(camera_number))

        processes = [
            CamGroupProcess(camera_ids=cam_id_subarray,
                            # latest_frames=self._latest_frames,
                            frame_lists_by_camera={camera_id: self._frame_lists_by_camera[camera_id] for camera_id in
                                                   cam_id_subarray},
                            camera_config_queues={camera_id: self._camera_config_queues[camera_id] for camera_id in
                                                  cam_id_subarray},
                            ) for cam_id_subarray in camera_group_subarrays
        ]
        cam_id_to_process = {}
        for process in processes:
            for cam_id in process.camera_ids:
                cam_id_to_process[cam_id] = process
        return processes, cam_id_to_process



    def _create_shared_memory_objects(self):
        self._shared_memory_manager = SharedCameraMemoryManager()

        # self._latest_frames = self._shared_memory_manager.create_camera_config_dictionary(camera_ids=self._camera_ids)
        self._frame_lists_by_camera = self._shared_memory_manager.create_frame_lists_by_camera(keys=self._camera_ids)

        self._folder_to_save_videos = self._shared_memory_manager.create_video_save_folder_list()

        self._camera_config_queues = self._shared_memory_manager.create_camera_config_queues(
            camera_ids=self._camera_ids)

    def update_camera_configs(self, camera_configs: Dict[str, CameraConfig]):
        for camera_id, camera_config_queue in self._camera_config_queues.items():
            camera_config_queue.put(camera_configs[camera_id])
