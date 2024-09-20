import multiprocessing
from multiprocessing.sharedctypes import Synchronized
from typing import Tuple, Union, List

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.memory.shared_memory_element import SharedMemoryElement


class SharedMemoryIndexedArrayDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    array_size: int
    shm_element_shape: Tuple[int, ...]
    dtype: np.dtype
    shm_element_names: List[str]
    last_written_index: Synchronized
    last_read_index: Synchronized


class SharedMemoryIndexedArray(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    array_size: int
    shm_element_shape: Tuple[int, ...]
    dtype: np.dtype
    shm_elements: List[SharedMemoryElement]
    last_written_index: Synchronized  # NOTE - represents APPARENT index of last written element from the User's perspective, we will internally handle wrapping around the array
    last_read_index: Synchronized  # NOTE - represents APPARENT index of last read element from the User's perspective, we will internally handle wrapping around the array

    @classmethod
    def create(cls,
               shm_element_shape: Tuple[int, ...],
               dtype: Union[np.dtype, type, str],
               array_size: int = 100,
               # TODO - calculate based on desired final size in memory rather than as an integer count of shm_elements
               ):
        dtype = cls._ensure_dtype(dtype)
        shm_elements = [SharedMemoryElement.create(shm_element_shape, dtype) for _ in range(array_size)]
        last_written_index = multiprocessing.Value('i', -1)
        last_read_index = multiprocessing.Value('i', -1)
        return cls(array_size=array_size,
                   shm_element_shape=shm_element_shape,
                   dtype=dtype,
                   shm_elements=shm_elements,
                   last_written_index=last_written_index,
                   last_read_index=last_read_index)

    @classmethod
    def recreate_from_dto(cls,
                          dto: SharedMemoryIndexedArrayDTO):
        dtype = cls._ensure_dtype(dto.dtype)
        shm_elements = [SharedMemoryElement.recreate(shm_name, dto.shm_element_shape, dtype) for shm_name in
                        dto.shm_element_names]

        return cls(array_size=dto.array_size,
                   shm_element_shape=dto.shm_element_shape,
                   dtype=dtype,
                   shm_elements=shm_elements,
                   last_written_index=dto.last_written_index,
                   last_read_index=dto.last_read_index)

    def to_dto(self) -> SharedMemoryIndexedArrayDTO:
        return SharedMemoryIndexedArrayDTO(
            array_size=self.array_size,
            shm_element_shape=self.shm_element_shape,
            dtype=self.dtype,
            shm_element_names=[element.shm.name for element in self.shm_elements],
            last_written_index=self.last_written_index,
            last_read_index=self.last_read_index
        )

    @property
    def new_data_available(self):
        return self.last_written_index.value != self.last_read_index.value

    @staticmethod
    def _ensure_dtype(dtype: Union[np.dtype, type, str]) -> np.dtype:
        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)
        return dtype

    def _check_overwrite(self, next_index: int) -> bool:
        return next_index % self.array_size == self.last_read_index.value % self.array_size

    def put_payload(self, array: np.ndarray):
        if array.shape != self.shm_element_shape:
            raise ValueError(
                f"Array shape {array.shape} does not match SharedMemoryIndexedArray shape {self.shm_element_shape}")
        if array.dtype != self.dtype:
            raise ValueError(f"Array dtype {array.dtype} does not match SharedMemoryIndexedArray dtype {self.dtype}")

        index_to_write = self.last_written_index.value + 1
        if self._check_overwrite(index_to_write):
            raise ValueError("Cannot overwrite data that hasn't been read yet.")

        self.shm_elements[index_to_write % self.array_size].copy_into_buffer(array)
        self.last_written_index.value = index_to_write

    def get_latest_payload(self) -> np.ndarray:
        """
        NOTE - this method does NOT update the 'last_read_index' value. It is intended to get the most up-to-date data (i.e. to keep the images displayed on the screen up-to-date),
         leaving the task of making sure we get ALL the data  without overwriting to the 'get_next_payload' method (i.e. making sure we save all the frames to disk/video).
        """
        if self.last_written_index.value == -1:
            raise ValueError("No payload has been written yet.")
        return self.shm_elements[self.last_written_index.value % self.array_size].copy_from_buffer()

    def get_next_payload(self) -> np.ndarray:
        index_to_read = self.last_read_index.value + 1
        shm_data = self.shm_elements[index_to_read % self.array_size].copy_from_buffer()
        self.last_read_index.value = index_to_read
        return shm_data

    def close(self):
        for element in self.shm_elements:
            element.close()

    def unlink(self):
        for element in self.shm_elements:
            element.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
