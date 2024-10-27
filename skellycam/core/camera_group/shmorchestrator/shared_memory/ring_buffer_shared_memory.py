import time
from dataclasses import dataclass
from typing import Tuple, Union, Optional

import numpy as np

from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_element import SharedMemoryElement
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_number import SharedMemoryNumber

ONE_GIGABYTE = 1024 ** 3


@dataclass
class SharedMemoryRingBufferDTO:
    dtype: np.dtype
    shm_element_name: str
    ring_buffer_shape: Tuple[int, ...]
    last_written_index_shm_name: str
    last_read_index_shm_name: str


@dataclass
class SharedMemoryRingBuffer:
    dtype: np.dtype
    ring_buffer_shm: SharedMemoryElement
    ring_buffer_shape: Tuple[int, ...]
    last_written_index: SharedMemoryNumber  # NOTE - represents APPARENT index of last written element from the User's perspective, we will internally handle wrapping around the array
    last_read_index: SharedMemoryNumber  # NOTE - represents APPARENT index of last read element from the User's perspective, we will internally handle wrapping around the array
    read_only: bool
    @classmethod
    def create(cls,
               example_payload: np.ndarray ,
               dtype: Union[np.dtype, type, str] = np.uint8,
               memory_allocation: int = ONE_GIGABYTE,
               ring_buffer_length: Optional[int] = None
               ):

        dtype = cls._ensure_dtype(dtype)
        if ring_buffer_length is None:
            ring_buffer_length = memory_allocation // np.prod(example_payload.shape)
        full_buffer = np.zeros((ring_buffer_length,) + example_payload.shape, dtype=dtype)
        ring_buffer_shm = SharedMemoryElement.create(full_buffer.shape, dtype)
        last_written_index = SharedMemoryNumber.create(initial_value=-1)
        last_read_index = SharedMemoryNumber.create(initial_value=-1)
        return cls(ring_buffer_shm=ring_buffer_shm,
                   ring_buffer_shape=full_buffer.shape,
                   dtype=dtype,
                   last_written_index=last_written_index,
                   last_read_index=last_read_index)

    @classmethod
    def recreate(cls,
                 dto: SharedMemoryRingBufferDTO):
        dtype = cls._ensure_dtype(dto.dtype)

        instance = cls(ring_buffer_shm=SharedMemoryElement.recreate(shm_name=dto.shm_element_name,
                                                                    shape=dto.ring_buffer_shape,
                                                                    dtype=dtype),
                       ring_buffer_shape=dto.ring_buffer_shape,
                       dtype=dtype,
                       last_written_index=SharedMemoryNumber.recreate(shm_name=dto.last_written_index_shm_name),
                       last_read_index=SharedMemoryNumber.recreate(shm_name=dto.last_read_index_shm_name))

        return instance



    def to_dto(self) -> SharedMemoryRingBufferDTO:
        return SharedMemoryRingBufferDTO(
            ring_buffer_shape=self.ring_buffer_shape,
            dtype=self.dtype,
            shm_element_name=self.ring_buffer_shm.name,
            last_written_index_shm_name=self.last_written_index.name,
            last_read_index_shm_name=self.last_read_index.name
        )

    @property
    def ready_to_read(self):
        return self.last_written_index.get() != -1

    @property
    def new_data_available(self):
        return self.last_written_index.get() != -1 and self.last_written_index.get() != self.last_read_index.get()

    @property
    def ring_buffer_length(self):
        return self.ring_buffer_shape[0]

    @staticmethod
    def _ensure_dtype(dtype: Union[np.dtype, type, str]) -> np.dtype:
        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)
        return dtype

    def _check_overwrite(self, next_index: int) -> bool:
        return next_index % self.ring_buffer_length == self.last_read_index.get() % self.ring_buffer_length

    def put_data(self, data: np.ndarray):

        if data.shape != self.ring_buffer_shape[1:]:
            raise ValueError(
                f"Array shape {data.shape} does not match SharedMemoryIndexedArray shape {self.ring_buffer_shape[1:]}")

        index_to_write = self.last_written_index.get() + 1
        if self._check_overwrite(index_to_write):
            raise ValueError("Cannot overwrite data that hasn't been read yet.")

        # self.shm_elements[index_to_write % self.ring_buffer_length].copy_into_buffer(array)
        self.ring_buffer_shm.buffer[index_to_write % self.ring_buffer_length] = data
        self.last_written_index.set(index_to_write)



    def get_next_payload(self) -> np.ndarray | None:
        if not self.new_data_available:
            raise ValueError("No new data available to read.")
        return self._read_next_payload()

    def _read_next_payload(self) -> np.ndarray| None:
        if self.last_written_index.get() == -1:
            return
        index_to_read = self.last_read_index.get() + 1
        shm_data = self.ring_buffer_shm.buffer[index_to_read % self.ring_buffer_length]
        self.last_read_index.set(index_to_read)
        return shm_data

    def get_latest_payload(self) -> np.ndarray | None:
        """
        NOTE - this method does NOT update the 'last_read_index' value.

        'Get Latest ...'  is intended to get the most up-to-date data (i.e. to keep the images displayed on the screen up-to-date)

        The task of making sure we get ALL the data without overwriting to the 'get_next_payload' method (i.e. making sure we save all the frames to disk/video).
        """
        if self.last_written_index.get() == -1:
            raise ValueError("No data available to read.")

        return self.ring_buffer_shm.buffer[self.last_written_index.get() % self.ring_buffer_length]

    def close(self):
        self.ring_buffer_shm.close()
        self.last_written_index.close()
        self.last_read_index.close()

    def unlink(self):
        self.ring_buffer_shm.unlink()
        self.last_written_index.unlink()
        self.last_read_index.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()




import multiprocessing
from time import sleep


def writer_process(ring_buffer_dto: SharedMemoryRingBufferDTO,
                   num_payloads: int,
                   payload_shape: Tuple[int, ...],
                   dtype: np.dtype):
    ring_buffer = SharedMemoryRingBuffer.recreate(ring_buffer_dto)
    time.sleep(1.0)
    for i in range(num_payloads):
        # Create test data
        data = np.full(payload_shape, i, dtype=dtype)
        try:
            time.sleep(0.1)
            ring_buffer.put_data(data)
            print(f"Writer: Written payload {i} with max value {data.max()}")
        except ValueError as e:
            print(f"Writer: {e}")
            # Sleep to simulate waiting for the reader to catch up
            sleep(0.1)

def reader_process(ring_buffer_dto: SharedMemoryRingBufferDTO, num_payloads: int):
    ring_buffer = SharedMemoryRingBuffer.recreate(ring_buffer_dto)
    read_data = []
    attempts = 0
    while attempts < 1e3:
        try:
            if ring_buffer.new_data_available:
                attempts = 0
                data = ring_buffer.get_next_payload()
                read_data.append(data)
                print(f"Reader: Read payload {ring_buffer.last_read_index.get()} with max value {data.max()}")
            else:
                attempts += 1
                sleep(0.001)
        except ValueError as e:
            print(f"Reader: {e}")
            # Sleep to simulate waiting for the writer to catch up
            sleep(0.1)
    return read_data

def tesst_shared_memory_ring_buffer_multiprocess():
    # Define parameters
    num_payloads = 10
    payload_shape = (100_000, 1000)

    # Test with np.ndarray payload
    dtype = np.uint8
    tesst_payload(np.ones(payload_shape, dtype=dtype), dtype, "np.ndarray", num_payloads)



def tesst_payload(example_payload, dtype, payload_type, num_payloads):
    print(f"Testing with {payload_type} payload")

    # Determine the shape to use for the writer process
    if isinstance(example_payload, np.ndarray):
        payload_shape = example_payload.shape
    else:
        # For bytes and str, use the original shape used to create the payload
        payload_shape = (100_000, 1000)

    # Create a ring buffer
    ring_buffer = SharedMemoryRingBuffer.create(
        example_payload=example_payload,
        dtype=dtype,
    )
    print(f"Ring buffer created with shape {ring_buffer.ring_buffer_shape} and dtype {ring_buffer.dtype}")

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

        print(f"Multi-process test completed for {payload_type}.")
    except Exception as e:
        print(f"Test failed for {payload_type}: {e}")
    finally:
        # Clean up shared memory
        ring_buffer.close_and_unlink()

if __name__ == "__main__":
    tesst_shared_memory_ring_buffer_multiprocess()