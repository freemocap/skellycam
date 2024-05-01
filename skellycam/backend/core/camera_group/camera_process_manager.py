from typing import Dict, List

from skellycam.backend.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.backend.core.camera_group.camera_process import (
    CameraProcess,
)
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 1

# https://refactoring.guru/design-patterns/strategy

import logging

logger = logging.getLogger(__name__)


class CameraProcessManager:
    def __init__(
            self,
            camera_configs: Dict[CameraId, CameraConfig],
    ):
        self._camera_configs = camera_configs
        self._camera_processes: Dict[CameraId, CameraProcess] = self._create_processes()

    def start_capture(self):
        logger.debug(f"Starting camera capture processes...")
        for process in self._camera_processes.values():
            process.start_capture()

    def stop_capture(self):
        logger.debug(f"Stopping camera capture processes...")
        for process in self._camera_processes.values():
            process.stop_capture()

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        for camera_id, process in self._camera_processes.items():
            new_frames.extend(process.get_new_frames())
        return new_frames

    def _create_processes(self) -> Dict[CameraId, CameraProcess]:
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras were provided")
        return {camera_id: CameraProcess(config)
                for camera_id, config in self._camera_configs.items()}

    def update_camera_configs(self, camera_configs :CameraConfigs):
        logger.info(f"Updating camera configs...")
        for camera_id, process in self._camera_processes.items():
            process.update_config(camera_configs[camera_id])
