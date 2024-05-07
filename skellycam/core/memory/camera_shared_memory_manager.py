import logging
from typing import Dict

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

BUFFER_SIZE = 1024 * 1024 * 1024  # 1 GB buffer size for all cameras

logger = logging.getLogger(__name__)


class CameraSharedMemoryManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 total_buffer_size: int = BUFFER_SIZE,
                 existing_shared_memory_names: Dict[CameraId, str] = None):
        self._camera_configs = camera_configs
        self._total_buffer_size = total_buffer_size
        self._buffer_size_per_camera = total_buffer_size // len(camera_configs)

        if existing_shared_memory_names is not None:
            if len(existing_shared_memory_names) != len(camera_configs):
                raise ValueError("The number of existing shared memory names must match the number of cameras")
        else:
            existing_shared_memory_names = {camera_id: None for camera_id in camera_configs.keys()}

        self._buffer_by_camera = {camera_id: CameraSharedMemory.from_config(camera_config=config,
                                                                            buffer_size=self._buffer_size_per_camera,
                                                                            shared_memory_name=existing_shared_memory_names[camera_id])
                                  for camera_id, config in self._camera_configs.items()}


def get_camera_shared_memory(self, camera_id: CameraId) -> CameraSharedMemory:
    return self._buffer_by_camera[camera_id]


def close(self):
    for camera_shared_memory in self._buffer_by_camera.values():
        camera_shared_memory.close()


def unlink(self):
    for camera_shared_memory in self._buffer_by_camera.values():
        camera_shared_memory.unlink()
