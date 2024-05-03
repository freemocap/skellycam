from typing import Dict, List

from skellycam.backend.core.cameras.camera_process import (
    CameraProcess,
)
from skellycam.backend.core.cameras.config.camera_config import CameraConfig, CameraConfigs
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

    @property
    def cameras_running(self) -> bool:
        return all(list(self._cameras_running_state().values()))

    def _cameras_running_state(self) -> Dict[CameraId, bool]:
        state = {camera_id: process.camera_ready for camera_id, process in self._camera_processes.items()}
        logger.trace(f"Cameras ready state: {state}")
        return state

    def start_cameras(self):
        logger.debug(f"Starting camera capture processes...")
        for process in self._camera_processes.values():
            process.start_capture()

    def stop_capture(self):
        logger.debug(f"Stopping camera capture processes...")
        for process in self._camera_processes.values():
            process.stop_capture()

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        log_string = "Found new frames: "
        for camera_id, process in self._camera_processes.items():
            log_string += f"{camera_id}: {len(process.get_new_frames())} "
            new_frames.extend(process.get_new_frames())
        logger.trace(log_string)
        return new_frames

    def _create_processes(self) -> Dict[CameraId, CameraProcess]:
        logger.debug(f"Creating camera processes...")
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras were provided")
        return {camera_id: CameraProcess(config)
                for camera_id, config in self._camera_configs.items()}

    def update_camera_configs(self, camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs...")
        for camera_id, process in self._camera_processes.items():
            process.update_config(camera_configs[camera_id])
