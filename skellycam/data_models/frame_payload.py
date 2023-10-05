from ctypes import c_wchar_p
import logging
from ctypes import c_wchar_p
from dataclasses import dataclass
from multiprocessing import Value
from multiprocessing.shared_memory import SharedMemory

import numpy as np





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
    success: Value  # success flag (bool)
    image_name: c_wchar_p  # shared memory block name (str)
    shape: tuple  # shape of the image (Union[Tuple[int, int, int], Tuple[int, int]])
    data_type: c_wchar_p  # data_type of the image (str)
    timestamp_ns: Value  # timestamp of the image (float)
    camera_id: c_wchar_p  # camera_id of the image (str)
    number_of_frames_received: Value  # number of frames received (int)


    @classmethod
    def from_data(cls, success: bool, image: np.ndarray, timestamp_ns: float, camera_id: str,
                  number_of_frames_received: int):
        shared_image_name, shape, data_type = cls.make_shared_memory_image(image)
        return cls(success=Value('b', success),
                   image_name=c_wchar_p(shared_image_name),
                   shape=shape,
                   data_type=data_type,
                   timestamp_ns=Value('f', timestamp_ns),
                   camera_id=c_wchar_p(camera_id),
                   number_of_frames_received=Value('i', number_of_frames_received))

    @staticmethod
    def make_shared_memory_image(image: np.ndarray):
        image_shared = SharedMemory(create=True, size=image.nbytes)
        np_array_shared = np.ndarray(image.shape, dtype=image.dtype, buffer=image_shared.buf)
        np.copyto(np_array_shared, image)
        return image_shared.name, image.shape, image.dtype

    def get_image(self):
        shared_memory = SharedMemory(name=self.image_name.value)
        np_array_shared = np.ndarray(self.shape, dtype=self.data_type, buffer=shared_memory.buf)
        return np_array_shared

    def unlink(self):
        shared_memory = SharedMemory(name=self.image_name.value)
        shared_memory.close()
        shared_memory.unlink()



if __name__ == "__main__":
    import skellycam
    skellycam.configure_logging()
    logger = logging.getLogger(__name__)

    dummy_image = np.random.randint(0, 255, (10, 20, 3), dtype=np.uint8)
    shared_payload = SharedMemoryFramePayload.from_data(success=True,
                                                        image=dummy_image,
                                                        timestamp_ns=123456789,
                                                        camera_id="test_camera",
                                                        number_of_frames_received=1)
    logger.info(f"Shared payload.image_name {shared_payload.image_name.value}")
    logger.info(f"Shared payload.get_image().shape {shared_payload.get_image().shape}")