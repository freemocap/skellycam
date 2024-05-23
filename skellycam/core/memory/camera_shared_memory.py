import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import Tuple, Union

import numpy as np
from pydantic import BaseModel, SkipValidation

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CameraSharedMemory(BaseModel):
    camera_config: CameraConfig
    buffer_size: int
    image_shape: Union[Tuple[int, int, int], Tuple[int, int]]
    bytes_per_pixel: int = BYTES_PER_PIXEL
    unhydrated_payload_size: int
    shm: shared_memory.SharedMemory
    lock: SkipValidation[multiprocessing.Lock]

    class Config:
        # TODO - do we need this? I think its giving deprecation warnings
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
    def camera_id(self):
        return self.camera_config.camera_id

    @property
    def image_size(self) -> int:
        return np.prod(self.image_shape) * self.bytes_per_pixel

    @property
    def shared_memory_name(self):
        return self.shm.name

    @property
    def payload_size(self) -> int:
        return self.image_size + self.unhydrated_payload_size

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
    def _calculate_buffer_sizes(camera_config: CameraConfig) -> Tuple[int, int, int]:
        image_resolution = camera_config.resolution
        color_channels = camera_config.color_channels
        if color_channels == 3:
            image_size = (image_resolution.height, image_resolution.width, color_channels)
        elif color_channels == 1:
            image_size = (image_resolution.height, image_resolution.width)
        else:
            raise ValueError(f"Unsupported number of color channels: {color_channels}")
        dummy_image = np.random.randint(0,
                                        255,
                                        size=image_size,
                                        dtype=np.uint8)

        dummy_unhydrated_frame = FramePayload.create_unhydrated_dummy(camera_id=camera_config.camera_id,
                                                                      image=dummy_image)

        dummy_frame_buffer = dummy_unhydrated_frame.to_buffer(dummy_image)

        image_size_in_bytes = len(dummy_image.tobytes())
        unhydrated_frame_size_in_bytes = len(dummy_unhydrated_frame.to_unhydrated_bytes())
        unhydrated_payload_number_of_bytes = len(dummy_frame_buffer) - image_size_in_bytes
        frame_buffer_size = len(dummy_frame_buffer)
        logger.debug(f"Calculated buffer size(s) for Camera {camera_config.camera_id} - \n"
                     f"\t\tImage Size[i]: {image_size_in_bytes:,d} bytes\n"
                     f"\t\tUnhydrated Frame Size[u]: {unhydrated_frame_size_in_bytes:,d} bytes\n"
                     f"\t\tFrame Buffer Size[f]: {frame_buffer_size:,d} bytes\n")

        return frame_buffer_size, image_size_in_bytes, unhydrated_payload_number_of_bytes

    def put_frame(self,
                  image: np.ndarray,
                  frame: FramePayload,
                  ):
        tik = time.perf_counter_ns()
        full_payload = self._frame_to_buffer_payload(image=image,
                                                     frame=frame)

        self.shm.buf[:] = full_payload  # this is where the magic happens

        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        logger.loop(
            f"Camera {self.camera_id} wrote frame #{frame.frame_number} to shared memory (took {elapsed_time_ms:.6}ms)")

    def retrieve_frame(self) -> Tuple[bytes, bytes]:
        tik = time.perf_counter_ns()

        payload_buffer = self.shm.buf[:]  # this is where the magic happens (in reverse)

        elapsed_get_from_shm = (time.perf_counter_ns() - tik) / 1e6
        image_bytes, unhydrated_frame_bytes = FramePayload.tuple_from_buffer(buffer=payload_buffer,
                                                                             image_shape=self.image_shape)

        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        elapsed_during_copy = elapsed_time_ms - elapsed_get_from_shm
        # logger.loop(f"Camera {self.camera_id} read frame #{frame.frame_number} "
        #             f"from shared memory (took {elapsed_get_from_shm:.6}ms "
        #             f"to get from shm buffer and {elapsed_during_copy:.6}ms to "
        #             f"copy, {elapsed_time_ms:.6}ms total")
        return image_bytes, unhydrated_frame_bytes

    def _frame_to_buffer_payload(self,
                                 frame: FramePayload,
                                 image: np.ndarray) -> bytes:
        if frame.hydrated:
            raise ValueError(f"Frame payload for {self.camera_id} should not be hydrated(i.e. have image data)")
        imageless_payload_bytes = frame.to_unhydrated_bytes()
        full_payload = image.tobytes() + imageless_payload_bytes
        if not len(full_payload) == self.payload_size:
            raise ValueError(
                f"Error converting frame to buffer payload! Size mismatch for {self.camera_id} on frame: {frame.frame_number} - "
                f"Expected: {self.payload_size}, "
                f"Actual: {len(full_payload)}")
        return full_payload

    def close(self):
        self.shm.close()
        self.shm.unlink()
        logger.debug(f"Closed and unlinked shared memory for Camera {self.camera_id}")
