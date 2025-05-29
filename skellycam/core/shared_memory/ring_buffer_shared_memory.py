from dataclasses import dataclass
from typing import Tuple, Optional

import numpy as np

from skellycam.core.shared_memory.shared_memory_element import SharedMemoryElement
from skellycam.core.shared_memory.shared_memory_number import SharedMemoryNumber

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
               example_payload: np.ndarray,
               dtype: np.dtype,
               read_only: bool,
               memory_allocation: int = ONE_GIGABYTE,
               ring_buffer_length: Optional[int] = None,
               ):
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
                   last_read_index=last_read_index,
                   read_only=read_only)

    @classmethod
    def recreate(cls,
                 dto: SharedMemoryRingBufferDTO,
                 read_only: bool):

        return cls(ring_buffer_shm=SharedMemoryElement.recreate(shm_name=dto.shm_element_name,
                                                                    shape=dto.ring_buffer_shape,
                                                                    dtype=dto.dtype),
                       ring_buffer_shape=dto.ring_buffer_shape,
                       dtype=dto.dtype,
                       last_written_index=SharedMemoryNumber.recreate(shm_name=dto.last_written_index_shm_name),
                       last_read_index=SharedMemoryNumber.recreate(shm_name=dto.last_read_index_shm_name),
                       read_only=read_only)


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
        return self.ready_to_read and self.last_written_index.get() > self.last_read_index.get()

    @property
    def ring_buffer_length(self):
        return self.ring_buffer_shape[0]

    def _check_for_overwrite(self, next_index: int) -> bool:
        return next_index % self.ring_buffer_length == self.last_read_index.get() % self.ring_buffer_length

    def put_data(self, data: np.ndarray):
        if self.read_only:
            raise ValueError("Cannot write to read-only SharedMemoryRingBuffer.")
        if data.shape != self.ring_buffer_shape[1:]:
            raise ValueError(
                f"Array shape {data.shape} does not match SharedMemoryIndexedArray shape {self.ring_buffer_shape[1:]}")

        index_to_write = self.last_written_index.value + 1
        if self._check_for_overwrite(index_to_write):
            raise ValueError("Cannot overwrite data that hasn't been read yet.")

        # self.shm_elements[index_to_write % self.ring_buffer_length].copy_into_buffer(array)
        self.ring_buffer_shm.buffer[index_to_write % self.ring_buffer_length] = data
        self.last_written_index.set(index_to_write)

    def get_next_payload(self) -> np.ndarray:
        if self.read_only:
            raise ValueError("Cannot call `get_next_payload` on read-only SharedMemoryRingBuffer. Use `get_latest_payload` instead.")
        if not self.ready_to_read:
            raise ValueError("Ring buffer is not ready to read yet.")
        if not self.new_data_available:
            raise ValueError("No new data available to read.")
        return self._read_next_payload()

    def _read_next_payload(self) -> np.ndarray | None:
        if self.last_written_index.get() == -1:
            raise ValueError("No data available to read.")
        index_to_read = self.last_read_index.value + 1
        if index_to_read > self.last_written_index.value:
            raise ValueError("Cannot read past the last written index!")
        shm_data = self.ring_buffer_shm.buffer[index_to_read % self.ring_buffer_length].copy()
        self.last_read_index.value = index_to_read
        return shm_data

    def get_latest_payload(self) -> np.ndarray:
        """
        NOTE - this method does NOT update the 'last_read_index' value.

        'Get Latest ...'  is intended to get the most up-to-date data (e.g. to keep the images displayed on the screen up-to-date)

        The task of making sure we get ALL the data without overwriting to the 'get_next_payload' method (e.g. making sure we save all the frames to disk/video).
        """
        if self.last_written_index.value == -1:
            raise ValueError("No data available to read.")

        return self.ring_buffer_shm.buffer[self.last_written_index.value % self.ring_buffer_length].copy()

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


