import enum
import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import List, Tuple, Union

import numpy as np
from pydantic import BaseModel, SkipValidation, Field

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class BufferFlagIndicies(enum.Enum):
    CAPTURE_STARTED: int = -1  # buffer index flipped from 0 to 255 on first write
    LAST_WRITTEN: int = -2  # index of the last written frame
    READ_NEXT: int = -3  # index of the next frame to read


class CameraSharedMemory(BaseModel):
    camera_config: CameraConfig
    buffer_size: int
    image_shape: Union[Tuple[int, int, int], Tuple[int, int]]
    bytes_per_pixel: int = BYTES_PER_PIXEL
    unhydrated_payload_size: int
    next_index: int = -1
    shm: shared_memory.SharedMemory
    lock: SkipValidation[multiprocessing.Lock]

    buffer_flag_indicies: BufferFlagIndicies = Field(default=BufferFlagIndicies)

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
        if not self.capture_started:
            return False
        return self.last_frame_written_index + 1 != self.read_next

    @property
    def capture_started(self) -> bool:
        return self.shm.buf[self.buffer_size + self.buffer_flag_indicies.CAPTURE_STARTED.value] == 255

    @capture_started.setter
    def capture_started(self, value: bool):
        with self.lock:
            if not value:
                raise ValueError(
                    "Can't unring the bell - once capture is started, it can't be stopped... only killed :O")
            self.shm.buf[self.buffer_size + self.buffer_flag_indicies.CAPTURE_STARTED.value] = 255 if value else 0

    @property
    def last_frame_written_index(self) -> int:
        return self.shm.buf[self.buffer_size + self.buffer_flag_indicies.LAST_WRITTEN.value]

    @last_frame_written_index.setter
    def last_frame_written_index(self, value: np.uint8):
        with self.lock:
            if not 0 <= value < 256:
                raise ValueError(f"Index {value} out of range for {self.camera_id}")
            self.shm.buf[self.buffer_size + self.buffer_flag_indicies.LAST_WRITTEN.value] = value

    @property
    def read_next(self) -> int:
        with self.lock:
            return self.shm.buf[self.buffer_size + self.buffer_flag_indicies.READ_NEXT.value]

    @read_next.setter
    def read_next(self, value: int):
        with self.lock:
            self.shm.buf[self.buffer_size + self.buffer_flag_indicies.READ_NEXT.value] = value % 256

    @property
    def image_size(self) -> int:
        return np.prod(self.image_shape) * self.bytes_per_pixel

    @property
    def shared_memory_name(self):
        return self.shm.name

    @property
    def payload_size(self) -> int:
        return self.image_size + self.unhydrated_payload_size

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
                f"RETRIEVING shared memory buffer for Camera{camera_id} - "
                f"(Name: {shared_memory_name}, Size: {buffer_size:,d} bytes)")
            return shared_memory.SharedMemory(name=shared_memory_name)
        else:

            shm = shared_memory.SharedMemory(create=True,
                                             size=int(buffer_size))
            logger.trace(
                f"CREATING shared memory buffer for Camera {camera_id} - "
                f"(Name: {shm.name}, Size: {buffer_size:,d} bytes)")
            return shm

    @staticmethod
    def _calculate_buffer_sizes(camera_config: CameraConfig,
                                payload_model: BaseModel = FramePayload) -> Tuple[int, int, int]:
        image_resolution = camera_config.resolution
        color_channels = camera_config.color_channels
        if color_channels == 3:
            image_size = (image_resolution.height, image_resolution.width, color_channels)
        elif color_channels == 1:
            image_size = (image_resolution.height, image_resolution.width)
        dummy_image = np.random.randint(0,
                                        255,
                                        size=image_size,
                                        dtype=np.uint8)

        dummy_frame = payload_model.create_hydrated_dummy(dummy_image)
        image_size_number_of_bytes = np.prod(dummy_image.shape) * BYTES_PER_PIXEL
        unhydrated_payload_number_of_bytes = len(dummy_frame.to_unhydrated_bytes())
        total_payload_size = image_size_number_of_bytes + unhydrated_payload_number_of_bytes

        # buffer size is 256 times the payload size so we can index with a uint8
        total_buffer_size = total_payload_size * (2 ** 8)
        total_buffer_size += 3  # add two more slots to store: capture-started, last-written and read-next indices
        logger.debug(f"Calculated buffer size(s) for Camera {camera_config.camera_id} - \n"
                     f"\t\tImage Size[i]: {image_size_number_of_bytes:,d} bytes\n"
                     f"\t\tUnhydrated Payload Size[u]: {unhydrated_payload_number_of_bytes:,d} bytes\n"
                     f"\t\tTotal Buffer Size [i + u] : {total_buffer_size:,d} bytes\n")

        return total_buffer_size, image_size_number_of_bytes, unhydrated_payload_number_of_bytes

    def put_frame(self,
                  frame: FramePayload,
                  image: np.ndarray):
        tik = time.perf_counter_ns()
        full_payload = self._frame_to_buffer_payload(frame, image)

        self.next_index += 1
        offset = self.offsets[self.next_index]
        if offset + self.payload_size > self.buffer_size:
            self.next_index = 0
            offset = self.offsets[self.next_index]

        if self.capture_started:
            self._check_for_overwrite()

        self.shm.buf[offset:offset + self.payload_size] = full_payload  # this is where the magic happens

        self.last_frame_written_index = self.next_index

        if not self.capture_started:
            self.capture_started = True

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

        payload_buffer = self.shm.buf[offset:offset + self.payload_size]  # this is where the magic happens (in reverse)

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
        frame = self.retrieve_frame(self.read_next)
        self.read_next += 1
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
        full_payload = image.tobytes() + imageless_payload_bytes
        if not len(full_payload) == self.payload_size:
            raise ValueError(f"Payload size mismatch for {self.camera_id} - "
                             f"Expected: {self.payload_size}, "
                             f"Actual: {len(full_payload)}")
        return full_payload

    def _check_for_overwrite(self, fail_on_overwrite: bool = False):
        if not self.last_frame_written_index == 0:
            if self.last_frame_written_index == self.read_next:
                if fail_on_overwrite:
                    raise ValueError(
                        f"Overwriting unread frame for {self.camera_id} and fail_on_overwrite is True - so... X_X")
                else:
                    logger.warning(
                        f"Overwriting unread frame for {self.camera_id}! "
                        f"The shared memory `writer` is lapping the `reader` -  "
                        f"use fewer cameras or decrease the resolution!")
