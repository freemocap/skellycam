import multiprocessing
import time
from dataclasses import dataclass
from typing import Tuple, Union

import numpy as np

from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_element import SharedMemoryElement


@dataclass
class SharedMemoryRingBufferDTO:
    dtype: np.dtype
    shm_element_name: str
    ring_buffer_shape: Tuple[int, ...]
    last_written_index: multiprocessing.Value
    last_read_index: multiprocessing.Value


@dataclass
class SharedMemoryRingBuffer:
    dtype: np.dtype
    ring_buffer_shm: SharedMemoryElement
    ring_buffer_shape: Tuple[int, ...]
    last_written_index: multiprocessing.Value  # NOTE - represents APPARENT index of last written element from the User's perspective, we will internally handle wrapping around the array
    last_read_index: multiprocessing.Value  # NOTE - represents APPARENT index of last read element from the User's perspective, we will internally handle wrapping around the array

    @classmethod
    def create(cls,
               example_buffer: np.ndarray | bytes | str,
               dtype: Union[np.dtype, type, str] = np.uint8,
               array_size: int = 100,
               # TODO - calculate based on desired final size in memory rather than as an integer count of shm_elements
               ):
        dtype = cls._ensure_dtype(dtype)
        if isinstance(example_buffer, np.ndarray):
            shm_element_shape = example_buffer.shape
        elif isinstance(example_buffer, bytes):
            shm_element_shape = np.frombuffer(example_buffer, dtype=dtype).shape
        elif isinstance(example_buffer, str):
            shm_element_shape = np.frombuffer(example_buffer.encode('utf-8'), dtype=dtype).shape
        else:
            raise ValueError(f"Unsupported type for 'example_buffer': {type(example_buffer)}")

        full_buffer = np.zeros((array_size,) + shm_element_shape, dtype=dtype)
        ring_buffer_shm = SharedMemoryElement.create(full_buffer.shape, dtype)
        last_written_index = multiprocessing.Value('i', -1)
        last_read_index = multiprocessing.Value('i', -1)
        return cls(ring_buffer_shm=ring_buffer_shm,
                   ring_buffer_shape=full_buffer.shape,
                   dtype=dtype,
                   last_written_index=last_written_index,
                   last_read_index=last_read_index)

    @classmethod
    def recreate_from_dto(cls,
                          dto: SharedMemoryRingBufferDTO):
        dtype = cls._ensure_dtype(dto.dtype)

        return cls(ring_buffer_shm=SharedMemoryElement.recreate(shm_name=dto.shm_element_name,
                                                                shape=dto.ring_buffer_shape,
                                                                dtype=dtype),
                   ring_buffer_shape=dto.ring_buffer_shape,
                   dtype=dtype,
                   last_written_index=dto.last_written_index,
                   last_read_index=dto.last_read_index)

    def to_dto(self) -> SharedMemoryRingBufferDTO:
        return SharedMemoryRingBufferDTO(
            ring_buffer_shape=self.ring_buffer_shape,
            dtype=self.dtype,
            shm_element_name=self.ring_buffer_shm.name,
            last_written_index=self.last_written_index,
            last_read_index=self.last_read_index
        )

    @property
    def new_data_available(self):
        return self.last_written_index.value != -1 and self.last_written_index.value != self.last_read_index.value

    @property
    def ring_buffer_length(self):
        return self.ring_buffer_shape[0]

    @staticmethod
    def _ensure_dtype(dtype: Union[np.dtype, type, str]) -> np.dtype:
        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)
        return dtype

    def _check_overwrite(self, next_index: int) -> bool:
        return next_index % self.ring_buffer_length == self.last_read_index.value % self.ring_buffer_length

    def put_payload(self, array: np.ndarray):
        if array.shape != self.ring_buffer_shape[1:]:
            raise ValueError(
                f"Array shape {array.shape} does not match SharedMemoryIndexedArray shape {self.ring_buffer_shape[1:]}")
        if array.dtype != self.dtype:
            raise ValueError(f"Array dtype {array.dtype} does not match SharedMemoryIndexedArray dtype {self.dtype}")

        index_to_write = self.last_written_index.value + 1
        if self._check_overwrite(index_to_write):
            raise ValueError("Cannot overwrite data that hasn't been read yet.")

        # self.shm_elements[index_to_write % self.ring_buffer_length].copy_into_buffer(array)
        self.ring_buffer_shm.buffer[index_to_write % self.ring_buffer_length] = array
        self.last_written_index.value = index_to_write

    def get_latest_payload(self) -> np.ndarray:
        """
        NOTE - this method does NOT update the 'last_read_index' value.

        'Get Latest ...'  is intended to get the most up-to-date data (i.e. to keep the images displayed on the screen up-to-date)

         The task of making sure we get ALL the data without overwriting to the 'get_next_payload' method (i.e. making sure we save all the frames to disk/video).
        """
        if self.last_written_index.value == -1:
            raise ValueError("No payload has been written yet.")
        return self.ring_buffer_shm.buffer[self.last_written_index.value % self.ring_buffer_length]

    def get_next_payload(self) -> np.ndarray | bytes | str:
        if not self.new_data_available:
            raise ValueError("No new data available.")

        index_to_read = self.last_read_index.value + 1
        shm_data = self.ring_buffer_shm.buffer[index_to_read % self.ring_buffer_length]
        self.last_read_index.value = index_to_read
        return shm_data

    def close(self):
        self.ring_buffer_shm.close()

    def unlink(self):
        self.ring_buffer_shm.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()


import multiprocessing
from time import sleep


def writer_process(ring_buffer_dto: SharedMemoryRingBufferDTO,
                   num_payloads: int,
                   payload_shape: Tuple[int, int],
                   dtype: np.dtype):
    ring_buffer = SharedMemoryRingBuffer.recreate_from_dto(ring_buffer_dto)
    time.sleep(1.0)
    for i in range(num_payloads):
        # Create test data
        data = np.full(payload_shape, i, dtype=dtype)
        try:
            time.sleep(0.1)
            ring_buffer.put_payload(data)
            print(f"Writer: Written payload {i} with max value {data.max()}")
        except ValueError as e:
            print(f"Writer: {e}")
            # Sleep to simulate waiting for the reader to catch up
            sleep(0.1)


def reader_process(ring_buffer_dto: SharedMemoryRingBufferDTO, num_payloads: int):
    ring_buffer = SharedMemoryRingBuffer.recreate_from_dto(ring_buffer_dto)
    read_data = []
    attempts = 0
    while attempts < 1e3:
        try:
            if ring_buffer.new_data_available:
                attempts = 0
                data = ring_buffer.get_next_payload()
                read_data.append(data)
                print(f"Reader: Read payload {ring_buffer.last_read_index.value} with max value {data.max()}")
            else:
                attempts += 1
                sleep(0.001)
        except ValueError as e:
            print(f"Reader: {e}")
            # Sleep to simulate waiting for the writer to catch up
            sleep(0.1)
    return read_data


def test_shared_memory_ring_buffer_multiprocess():
    # Define parameters
    array_size = 5
    num_payloads = 10
    payload_shape = (3, 3)
    dtype = np.uint8

    # Create a ring buffer
    ring_buffer = SharedMemoryRingBuffer.create(
        example_buffer=np.ones(payload_shape, dtype=dtype),
        dtype=dtype,
        array_size=array_size
    )

    # Start writer and reader processes
    writer = multiprocessing.Process(target=writer_process, args=(ring_buffer.to_dto(),
                                                                  num_payloads,
                                                                  payload_shape,
                                                                  dtype))
    reader = multiprocessing.Process(target=reader_process, args=(ring_buffer.to_dto(),
                                                                  num_payloads))

    try:
        writer.start()
        reader.start()

        writer.join()
        reader.join()

        print("Multi-process test completed.")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Clean up shared memory
        ring_buffer.close_and_unlink()


if __name__ == "__main__":
    test_shared_memory_ring_buffer_multiprocess()
