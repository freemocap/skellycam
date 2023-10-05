import multiprocessing
from dataclasses import dataclass
from multiprocessing import Value
from multiprocessing.shared_memory import SharedMemory
from typing import Union, Tuple

import numpy as np
import logging
logger = logging.getLogger(__name__)

@dataclass
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    camera_id: str = None
    number_of_frames_received: int = None

    @classmethod
    def from_shared_memory_frame_payload(cls,
                                         shared_memory_frame_payload: 'SharedMemoryFramePayload',
                                         unlink_shared_memory: bool = False):
        image = shared_memory_frame_payload.get_image()
        if unlink_shared_memory:
            shared_memory_frame_payload.unlink()
        return cls(success=shared_memory_frame_payload.success.value,
                   image=image,
                   timestamp_ns=shared_memory_frame_payload.timestamp_ns.value,
                   camera_id=shared_memory_frame_payload.camera_id.value,
                   number_of_frames_received=shared_memory_frame_payload.number_of_frames_received.value)

@dataclass
class SharedMemoryFramePayload:
    """
    This is the payload that is shared between processes. Instead of passing the image data, we pass the shared memory block name.
    """
    success: multiprocessing.Value  # success flag (bool)
    image_name: multiprocessing.Value  # shared memory block name (str)
    shape: multiprocessing.Value  # shape of the image (Union[Tuple[int, int, int], Tuple[int, int]])
    data_type: multiprocessing.Value  # data_type of the image (str)
    timestamp_ns: multiprocessing.Value  # timestamp of the image (float)
    camera_id: multiprocessing.Value  # camera_id of the image (str)
    number_of_frames_received: multiprocessing.Value  # number of frames received (int)

    @classmethod
    def from_data(cls,
                  success: bool,
                  image: np.ndarray,
                  timestamp_ns: float,
                  camera_id: str,
                  number_of_frames_received: int):
        image_name, shape, data_type = cls.make_shared_memory_image(image)
        return cls(success=Value('b', success),
                   image_name=Value('s', image_name),
                   shape=Value('i', shape),
                   data_type=Value('s', data_type),
                   timestamp_ns=Value('f', timestamp_ns),
                   camera_id=Value('s', camera_id),
                   number_of_frames_received=Value('i', number_of_frames_received))

    @classmethod
    def make_shared_memory_image(cls, image) -> (str,
                                                 Union[Tuple[int, int, int], Tuple[int, int]],
                                                 str):
        try:
            shared_memory = SharedMemory(create=True, size=image.nbytes)
            np_array_shared = np.ndarray(image.shape, dtype=image.dtype, buffer=shared_memory.buf)
            np.copyto(np_array_shared, image)
            return shared_memory.name, image.shape, str(image.dtype)
        except Exception as e:
            logger.error("Failed to create shared memory: ", e)
            logger.exception(e)
            raise e

    def get_image(self) -> np.ndarray:
        try:
            shared_memory = SharedMemory(name=self.image_name.value)
            np_array_shared = np.ndarray(self.shape.value, dtype=self.data_type.value, buffer=shared_memory.buf)
            return np_array_shared
        except Exception as e:
            logger.error("Failed to get image from shared memory: ", e)
            logger.exception(e)
            raise e

    def unlink(self):
        try:
            shared_memory = SharedMemory(name=self.image_name.value)
            shared_memory.unlink()
        except Exception as e:
            logger.error("Failed to unlink shared memory: ", e)
            logger.exception(e)
            raise e