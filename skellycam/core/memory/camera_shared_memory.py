import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import List, Tuple

import numpy as np
from pydantic import BaseModel, SkipValidation, Field

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
    next_index: int = -1
    shm: shared_memory.SharedMemory
    lock: SkipValidation[multiprocessing.Lock]

    last_written_flag_buffer_index: int = Field(default=-1,
                                                description="This index in the `buffer` is used to store the index of the last frame written")
    last_read_flag_buffer_index: int = Field(default=-2,
                                             description="This index in the `buffer` is used to store the index of the last frame read")

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_config(cls,
                    camera_config: CameraConfig,
                    lock: multiprocessing.Lock,
                    shared_memory_name: str = None,
                    ):
        total_buffer_size, image_size, unhydrated_payload_size = cls._calculate_buffer_sizes(camera_config)

        shm = cls._get_or_create_shared_memory(camera_id=camera_config.camera_id,
                                               buffer_size=total_buffer_size,
                                               shared_memory_name=shared_memory_name)

        return cls(camera_config=camera_config,
                   image_shape=camera_config.image_shape,
                   buffer_size=total_buffer_size,
                   unhydrated_payload_size=unhydrated_payload_size,
                   shm=shm,
                   lock=lock)

    @property
    def new_frame_available(self) -> bool:
        if self.last_frame_written_index == 0 and self.frame_to_read == 0:
            # this is to check if the first frame has been written,
            # AFAICT - it could technically return incorrectly when the read/write indices wrap around,
            # but it would resolve itself on the next write
            return False
        return self.last_frame_written_index != self.frame_to_read

    @property
    def last_frame_written_index(self) -> int:
        with self.lock:
            return self.shm.buf[self.buffer_size + self.last_written_flag_buffer_index]

    @last_frame_written_index.setter
    def last_frame_written_index(self, value: np.uint8):
        with self.lock:
            if not 0 <= value < 256:
                raise ValueError(f"Index {value} out of range for {self.camera_id}")
            self.shm.buf[self.buffer_size + self.last_written_flag_buffer_index] = value

    @property
    def frame_to_read(self) -> int:
        with self.lock:
            return self.shm.buf[self.buffer_size + self.last_read_flag_buffer_index]

    @frame_to_read.setter
    def frame_to_read(self, value: np.uint8):
        with self.lock:
            if not 0 <= value < 256:
                raise ValueError(f"Index {value} out of range for {self.camera_id}")
            self.shm.buf[self.buffer_size + self.last_read_flag_buffer_index] = value

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
                f"RETRIEVING shared memory buffer for Camera{camera_id} - (Name: {shared_memory_name}, Size: {buffer_size:,d} bytes)")
            return shared_memory.SharedMemory(name=shared_memory_name)
        else:

            shm = shared_memory.SharedMemory(create=True,
                                             size=int(buffer_size))
            logger.trace(
                f"CREATING shared memory buffer for Camera {camera_id} - (Name: {shm.name}, Size: {buffer_size:,d} bytes)")
            return shm

    @staticmethod
    def _calculate_buffer_sizes(camera_config: CameraConfig,
                                payload_model: BaseModel = FramePayload) -> Tuple[int, int, int]:
        image_resolution = camera_config.resolution
        color_channels = camera_config.color_channels
        dummy_image = np.random.randint(0,
                                        255,
                                        size=(image_resolution.height, image_resolution.width, color_channels),
                                        dtype=np.uint8)
        dummy_frame = payload_model.create_dummy()
        image_size_number_of_bytes = np.prod(dummy_image.shape) * BYTES_PER_PIXEL
        unhydrated_payload_number_of_bytes = len(dummy_frame.to_unhydrated_bytes())
        total_payload_size = image_size_number_of_bytes + unhydrated_payload_number_of_bytes

        # buffer size is 256 times the payload size so we can index with a uint8
        total_buffer_size = total_payload_size * (2 ** 8)
        total_buffer_size += 2  # add two more slots to store the last written and last read indices
        logger.debug(f"Calculated buffer size(s) for Camera {camera_config.camera_id} - \n"
                     f"\t\tImage Size[i]: {image_size_number_of_bytes:,d} bytes\n"
                     f"\t\tUnhydrated Payload Size[u]: {unhydrated_payload_number_of_bytes:,d} bytes\n"
                     f"\t\tTotal Buffer Size [i + u] : {total_buffer_size:,d} bytes\n")

        return total_buffer_size, image_size_number_of_bytes, unhydrated_payload_number_of_bytes


class CameraSharedMemory(CameraSharedMemoryModel):
    def put_frame(self,
                  frame: FramePayload,
                  image: np.ndarray):
        tik = time.perf_counter_ns()
        full_payload = self._frame_to_buffer_payload(frame, image)

        initial_frame = False
        if self.next_index == -1:
            initial_frame = True

        self.next_index += 1
        offset = self.offsets[self.next_index]
        if offset + self.payload_size > self.buffer_size:
            self.next_index = 0
            offset = self.offsets[self.next_index]

        if not initial_frame:
            self._check_for_overwrite()

        self.shm.buf[offset:offset + self.payload_size] = full_payload
        self.last_frame_written_index = self.next_index
        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        logger.loop(
            f"Camera {self.camera_id} wrote frame #{frame.frame_number} to shared memory at "
            f"index#{self.next_index} (offset: {offset} bytes, took {elapsed_time_ms}ms,"
            f" checksum:{np.sum(np.frombuffer(full_payload, dtype=np.uint8))}\n"
            f"{frame}")

    def retrieve_frame(self, index: int) -> FramePayload:
        tik = time.perf_counter_ns()
        if index >= len(self.offsets) or index < 0:
            raise ValueError(f"Index {index} out of range for {self.camera_id}")
        offset = self.offsets[index]
        payload_buffer = self.shm.buf[offset:offset + self.payload_size]
        elapsed_get_from_shm = (time.perf_counter_ns() - tik) / 1e6
        frame = FramePayload.from_buffer(buffer=payload_buffer,
                                         image_shape=self.image_shape)
        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        elapsed_during_copy = elapsed_time_ms - elapsed_get_from_shm
        logger.loop(f"Camera {self.camera_id} read frame #{frame.frame_number} "
                    f"from shared memory at index#{index} "
                    f"(offset: {offset} bytes, took {elapsed_get_from_shm}ms "
                    f"to get from shm buffery and {elapsed_during_copy}ms to "
                    f"copy, {elapsed_time_ms}ms total, checksum: {np.sum(payload_buffer)})\n")
        return frame

    def get_next_frame(self) -> FramePayload:
        frame = self.retrieve_frame(self.frame_to_read)
        self.frame_to_read += 1
        return frame

    def get_latest_frame(self) -> FramePayload:
        frame = self.retrieve_frame(self.last_frame_written_index)
        return frame

    def _increment_index(self):
        self.next_index += 1
        if self.next_index >= len(self.offsets):
            self.next_index = 0

    def _frame_to_buffer_payload(self,
                                 frame: FramePayload,
                                 image: np.ndarray) -> bytes:
        if frame.hydrated:
            raise ValueError(f"Frame payload for {self.camera_id} should not be hydrated(i.e. have image data)")
        imageless_payload_bytes = frame.to_unhydrated_bytes()
        full_payload = imageless_payload_bytes + image.tobytes()
        if not len(full_payload) == self.payload_size:
            raise ValueError(f"Payload size mismatch for {self.camera_id} - "
                             f"Expected: {self.payload_size}, "
                             f"Actual: {len(full_payload)}")
        return full_payload

    def _check_for_overwrite(self, fail_on_overwrite: bool = False):
        if not self.last_frame_written_index == 0:
            if self.last_frame_written_index == self.frame_to_read:
                if fail_on_overwrite:
                    raise ValueError(
                        f"Overwriting unread frame for {self.camera_id} and fail_on_overwrite is True - so... X_X")
                else:
                    logger.warning(
                        f"Overwriting unread frame for {self.camera_id}! The shared memory `writer` is lapping the `reader` - use fewer cameras or decrease the resolution!")
