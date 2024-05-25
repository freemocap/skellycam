import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import Tuple, Union, Optional

import numpy as np
from pydantic import BaseModel, SkipValidation, ConfigDict

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CameraSharedMemory(BaseModel):
    camera_config: CameraConfig
    image_shape: Union[Tuple[int, int, int], Tuple[int, int]]
    bytes_per_pixel: int = BYTES_PER_PIXEL
    unhydrated_payload_size: int
    image_buffer_size: int
    total_frame_buffer_size: int
    shm: shared_memory.SharedMemory
    lock: SkipValidation[multiprocessing.Lock]
    model_config = ConfigDict(arbitrary_types_allowed=True)


    @classmethod
    def from_config(cls,
                    camera_config: CameraConfig,
                    lock: multiprocessing.Lock,
                    shared_memory_name: str = None,
                    ):
        total_frame_buffer_size, image_size, unhydrated_payload_size = cls._calculate_payload_buffer_sizes(
            camera_config)

        shm = cls._get_or_create_shared_memory(camera_id=camera_config.camera_id,
                                               total_frame_buffer_size=total_frame_buffer_size,
                                               shared_memory_name=shared_memory_name)


        return cls(camera_config=camera_config,
                   image_shape=camera_config.image_shape,
                   unhydrated_payload_size=unhydrated_payload_size,
                   image_buffer_size=image_size,
                   total_frame_buffer_size=total_frame_buffer_size,
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
    def shared_memory_size(self):
        return self.shm.size

    @classmethod
    def _get_or_create_shared_memory(cls,
                                     camera_id: CameraId,
                                     total_frame_buffer_size: int,
                                     shared_memory_name: Optional[str]):
        if shared_memory_name is not None:  # get existing shared memory

            shm = shared_memory.SharedMemory(name=shared_memory_name)
            logger.trace(
                f"RETRIEVING shared memory buffer for Camera{camera_id} - "
                f"(Name: {shared_memory_name}, Size: {shm.size:,d} bytes)")

        else:  # create new shared memory
            init_shm = shared_memory.SharedMemory(create=True,
                                                  size=int(total_frame_buffer_size))

            # recreate so we can be sure the sizes match
            shm = shared_memory.SharedMemory(name=init_shm.name)
            init_shm.close()
            logger.trace(
                f"CREATING shared memory buffer for Camera {camera_id} - "
                f"(Name: {shm.name}, Size: {shm.size:,d} bytes)")
        if total_frame_buffer_size > shm.size:
            raise ValueError(
                f"Shared memory buffer size is too small for Camera {camera_id} - "
                f"Expected: {total_frame_buffer_size:,d} bytes, "
                f"Actual: {shm.size:,d} bytes")
        return shm

    @staticmethod
    def _calculate_payload_buffer_sizes(camera_config: CameraConfig) -> Tuple[int, int, int]:
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
        total_frame_buffer_size = len(dummy_frame_buffer)
        logger.debug(f"Calculated buffer size(s) for Camera {camera_config.camera_id} - \n"
                     f"\t\tImage Size[i]: {image_size_in_bytes:,d} bytes\n"
                     f"\t\tUnhydrated Frame Size[u]: {unhydrated_frame_size_in_bytes:,d} bytes\n"
                     f"\t\tFrame Buffer Size[f]: {total_frame_buffer_size:,d} bytes\n")

        return total_frame_buffer_size, image_size_in_bytes, unhydrated_payload_number_of_bytes

    def put_new_frame(self,
                      image: np.ndarray,
                      frame: FramePayload,
                      ):
        tik = time.perf_counter_ns()
        full_payload = frame.to_buffer(image=image)
        self.shm.buf[:self.total_frame_buffer_size] = full_payload

        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        logger.loop(
            f"Camera {self.camera_id} wrote frame #{frame.frame_number} to shared memory (took {elapsed_time_ms:.6}ms)")

    def move_latest_frame_to_read_buffer(self,
                      image: np.ndarray,
                      frame: FramePayload,
                      ):
        tik = time.perf_counter_ns()
        full_payload = frame.to_buffer(image=image)
        self.shm.buf[:self.total_frame_buffer_size] = full_payload

        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        logger.loop(
            f"Camera {self.camera_id} wrote frame #{frame.frame_number} to shared memory (took {elapsed_time_ms:.6}ms)")

    def retrieve_frame(self) -> memoryview:
        tik = time.perf_counter_ns()

        payload_buffer_mv = self.shm.buf[:self.total_frame_buffer_size]  # this is where the magic happens (in reverse)

        elapsed_get_from_shm = (time.perf_counter_ns() - tik) / 1e6
        # image_bytes, unhydrated_frame_bytes = FramePayload.tuple_from_buffer(buffer=payload_buffer,
        #                                                                      image_shape=self.image_shape)

        elapsed_time_ms = (time.perf_counter_ns() - tik) / 1e6
        elapsed_during_copy = elapsed_time_ms - elapsed_get_from_shm
        # logger.loop(f"Camera {self.camera_id} read frame #{frame.frame_number} "
        #             f"from shared memory (took {elapsed_get_from_shm:.6}ms "
        #             f"to get from shm buffer and {elapsed_during_copy:.6}ms to "
        #             f"copy, {elapsed_time_ms:.6}ms total")
        return payload_buffer_mv



    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()
