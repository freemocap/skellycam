import logging
import multiprocessing
from multiprocessing import shared_memory
from typing import List, Tuple

import numpy as np
from pydantic import BaseModel, PrivateAttr, SkipValidation

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CameraSharedMemoryModel(BaseModel):
    camera_config: CameraConfig
    buffer_size: int
    image_shape: Tuple[int, int, int]
    bytes_per_pixel: int = BYTES_PER_PIXEL
    unhydrated_payload_size: int
    next_index: int = 0
    shm: shared_memory.SharedMemory
    lock: SkipValidation[multiprocessing.Lock]

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_config(cls,
                    camera_config: CameraConfig,
                    lock: multiprocessing.Lock,
                    shared_memory_name: str = None,
                    **kwargs
                    ):
        total_buffer_size, image_size, unhydrated_payload_size = cls._calculate_buffer_sizes(camera_config)

        shm = cls._get_or_create_shared_memory(camera_id=camera_config.camera_id,
                                               buffer_size=total_buffer_size,
                                               shared_memory_name=shared_memory_name)

        return cls(camera_config=camera_config,
                   buffer_size=total_buffer_size,
                   image_shape=camera_config.image_shape,
                   unhydrated_payload_size=unhydrated_payload_size,
                   shm=shm,
                   lock=lock,
                   **kwargs)

    @property
    def new_frame_available(self) -> bool:
        with self.lock:
            return self.shm.buf[self.buffer_size - 1] == 1

    @new_frame_available.setter
    def new_frame_available(self, value: bool):
        with self.lock:
            self.shm.buf[self.buffer_size - 1] = 1 if value else 0

    @property
    def last_frame_written_index(self) -> int:
        with self.lock:
            return self.shm.buf[self.buffer_size - 2]

    @last_frame_written_index.setter
    def last_frame_written_index(self, value: np.uint8):
        with self.lock:
            if not 0 <= value < 256:
                raise ValueError(f"Index {value} out of range for {self.camera_id}")
            self.shm.buf[self.buffer_size - 2] = value

    @property
    def last_frame_read_index(self) -> int:
        with self.lock:
            return self.shm.buf[self.buffer_size - 3]

    @last_frame_read_index.setter
    def last_frame_read_index(self, value: np.uint8):
        with self.lock:
            if not 0 <= value < 256:
                raise ValueError(f"Index {value} out of range for {self.camera_id}")
            self.shm.buf[self.buffer_size - 3] = value

    @property
    def image_size(self) -> int:
        return np.prod(self.image_shape) * self.bytes_per_pixel

    @property
    def shared_memory_name(self):
        return self.shm.name

    @property
    def payload_size(self) -> int:
        return self.unhydrated_payload_size + self.image_size

    @property
    def offsets(self) -> List[int]:
        return list(np.arange(0, self.buffer_size, self.payload_size))

    @property
    def camera_id(self):
        return self.camera_config.camera_id

    @classmethod
    def _get_or_create_shared_memory(cls,
                                     camera_id: CameraId,
                                     buffer_size: int,
                                     shared_memory_name: str):
        if shared_memory_name:
            logger.trace(
                f"RETRIEVING shared memory buffer for Camera{camera_id} - (Name: {shared_memory_name}, Size: {buffer_size})")
            return shared_memory.SharedMemory(name=shared_memory_name)
        else:
            logger.trace(
                f"CREATING shared memory buffer for Camera {camera_id} - (Name: {shared_memory_name}, Size: {buffer_size})")
            return shared_memory.SharedMemory(create=True,
                                              size=int(buffer_size))

    @staticmethod
    def _calculate_buffer_sizes(camera_config: CameraConfig,
                                payload_model: BaseModel = FramePayload) -> Tuple[int, int, int]:
        image_resolution = camera_config.resolution
        color_channels = camera_config.color_channels
        dummy_image = np.random.randint(0,
                                        255,
                                        size=(image_resolution.height, image_resolution.width, color_channels),
                                        dtype=np.uint8)
        dummy_frame = payload_model.create_dummy(image=dummy_image)
        image_size_number_of_bytes = np.prod(dummy_image.shape) * BYTES_PER_PIXEL
        unhydrated_payload_number_of_bytes = len(dummy_frame.to_unhydrated_bytes())
        total_payload_size = image_size_number_of_bytes + unhydrated_payload_number_of_bytes
        total_buffer_size = total_payload_size * 2 ** 8  # buffer size is 256 times the payload size, so we can index with a uint8 lol
        total_buffer_size += 3  # [-1]: new data available, [-2]: last read index, [-3]: last write index
        return total_buffer_size, image_size_number_of_bytes, unhydrated_payload_number_of_bytes


class CameraSharedMemory(CameraSharedMemoryModel):
    def put_frame(self,
                  frame: FramePayload,
                  image: np.ndarray):

        if frame.hydrated:
            raise ValueError(f"Frame payload for {self.camera_id} should not be hydrated(i.e. have image data)")

        imageless_payload_bytes = frame.to_unhydrated_bytes()
        full_payload = imageless_payload_bytes + image.tobytes()
        if not len(full_payload) == self.payload_size:
            raise ValueError(f"Payload size mismatch for {self.camera_id} - "
                             f"Expected: {self.payload_size}, "
                             f"Actual: {len(full_payload)}")
        offset = self.offsets[self.next_index]
        if offset + self.payload_size > self.buffer_size:
            self.next_index = 0
            offset = self.offsets[self.next_index]

        self.shm.buf[offset:offset + self.payload_size] = full_payload
        self.last_frame_written_index = self.next_index

        if not self.last_frame_written_index == 0:
            if self.last_frame_written_index == self.last_frame_read_index:
                logger.warning(f"Overwriting unread frame for {self.camera_id}! Shared memory buffer is full!")

        self.new_frame_available = True
        logger.loop(f"Camera {self.camera_id} wrote frame #{frame.frame_number}) to shared memory at index#{self.next_index} offset {offset}\n{frame}")
        self.next_index += 1

    def retrieve_frame(self, index: int) -> FramePayload:
        if index >= len(self.offsets) or index < 0:
            raise ValueError(f"Index {index} out of range for {self.camera_id}")
        offset = self.offsets[index]
        payload_buffer = self.shm.buf[offset:offset + self.payload_size]
        frame = FramePayload.from_buffer(buffer=payload_buffer,
                                         image_shape=self.image_shape)
        self.last_frame_read_index = index
        if self.last_frame_read_index == self.last_frame_written_index:
            self.new_frame_available = False
        logger.loop(f"Camera {self.camera_id} read frame ({frame}) from shared memory at offset {offset}")
        return frame

    def get_next_frame(self) -> FramePayload:
        frame = self.retrieve_frame(self.last_frame_read_index)
        return frame

    def get_latest_frame(self) -> FramePayload:
        frame = self.retrieve_frame(self.last_frame_written_index)
        return frame

    def _increment_index(self):
        self.next_index += 1
        if self.next_index >= len(self.offsets):
            self.next_index = 0
