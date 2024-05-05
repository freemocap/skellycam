import asyncio
from typing import Dict, List

from skellycam.backend.core.cameras.camera_process import (
    CameraProcess,
)
from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload


import logging

logger = logging.getLogger(__name__)


class CameraProcessManager:
    def __init__(
            self,
    ):
        self._camera_configs: CameraConfigs = {}
        self._camera_processes: Dict[CameraId, CameraProcess] = {}

    @property
    def camera_ids(self):
        return list(self._camera_processes.keys())

    def set_camera_configs(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._camera_processes = self._create_processes()

    async def start_cameras(self):
        if len(self._camera_processes) == 0:
            raise ValueError("No cameras to start!")

        logger.debug(f"Starting camera capture processes...")
        await asyncio.gather(*(process.start_process()
                               for process in self._camera_processes.values()))
        logger.debug(f"All camera capture processes ready - starting capture...")
        for process in self._camera_processes.values():
            process.start_capture()

    def close(self):
        logger.debug(f"Stopping camera capture processes...")
        if len(self._camera_processes) == 0:
            logger.debug("No cameras to close!")
            return
        for process in self._camera_processes.values():
            process.stop_capture()

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        for camera_id, process in self._camera_processes.items():
            new_frames.extend(process.get_new_frames())
        return new_frames

    def _create_processes(self) -> Dict[CameraId, CameraProcess]:
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras to create processes for!")
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras were provided")
        return {camera_id: CameraProcess(config)
                for camera_id, config in self._camera_configs.items()}

    async def update_camera_configs(self, camera_configs: CameraConfigs, strict: bool = False):
        logger.info(f"Updating camera configs...")
        update_tasks = []
        for camera_id, process in self._camera_processes.items():
            update_tasks.append(asyncio.create_task(process.update_config(camera_configs[camera_id], strict)))

        await asyncio.gather(*update_tasks)
