import logging
import multiprocessing
from multiprocessing import connection
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


class CameraSharedMemoryManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 lock: multiprocessing.Lock,
                 existing_shared_memory_names: Dict[CameraId, str] = None):
        self._camera_configs = camera_configs
        self._lock = lock

        if existing_shared_memory_names is not None:
            if len(existing_shared_memory_names) != len(camera_configs):
                raise ValueError("The number of existing shared memory names must match the number of cameras")
        else:
            existing_shared_memory_names = {camera_id: None for camera_id in camera_configs.keys()}

        self._camera_shms = {camera_id: CameraSharedMemory.from_config(camera_config=config,
                                                                       lock=self._lock,
                                                                       shared_memory_name=
                                                                            existing_shared_memory_names[camera_id])
                             for camera_id, config in self._camera_configs.items()}

    @property
    def camera_configs(self) -> CameraConfigs:
        return self._camera_configs

    @property
    def shared_memory_names(self) -> Dict[CameraId, str]:
        return {camera_id: camera_shared_memory.shared_memory_name for camera_id, camera_shared_memory in
                self._camera_shms.items()}

    @property
    def shared_memory_sizes(self) -> Dict[CameraId, int]:
        return {camera_id: camera_shared_memory.shared_memory_size for camera_id, camera_shared_memory in
                self._camera_shms.items()}
    @property
    def lock(self) -> multiprocessing.Lock:
        return self._lock

    @property
    def total_buffer_size(self) -> int:
        return sum([camera_shared_memory.buffer_size for camera_shared_memory in self._camera_shms.values()])

    def get_multi_frame_payload(self,
                              previous_payload: MultiFramePayload) -> MultiFramePayload:
        payload = MultiFramePayload.from_previous(previous_payload)

        for camera_id, camera_shared_memory in self._camera_shms.items():
            frame_buffer_mv = camera_shared_memory.retrieve_frame()
            frame = FramePayload.from_buffer(buffer=frame_buffer_mv,
                                             image_shape=camera_shared_memory.image_shape)
            payload.add_frame(frame)

        if not payload.full:
            raise ValueError("Did not read full multi-frame payload!")
        return payload


    def get_camera_shared_memory(self, camera_id: CameraId) -> CameraSharedMemory:
        return self._camera_shms[camera_id]

    def close(self):
        for camera_shared_memory in self._camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        for camera_shared_memory in self._camera_shms.values():
            camera_shared_memory.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
