from multiprocessing import shared_memory
from typing import Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict

class SharedMemoryElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    buffer: np.ndarray
    dtype: np.dtype
    shm: shared_memory.SharedMemory
    original_shape: Tuple[int, ...]

    @classmethod
    def create(cls, shape: Tuple[int, ...], dtype: Union[np.dtype, type, str]):
        dtype = cls._ensure_dtype(dtype)
        payload_size_bytes = int(np.prod(shape) * dtype.itemsize)
        shm = shared_memory.SharedMemory(size=payload_size_bytes, create=True)
        buffer = np.ndarray((payload_size_bytes // dtype.itemsize,), dtype=dtype, buffer=shm.buf)
        return cls(buffer=buffer, shm=shm, dtype=dtype, original_shape=shape)

    @classmethod
    def recreate(cls, shm_name: str, shape: tuple, dtype: np.dtype):
        dtype = cls._ensure_dtype(dtype)
        shm = shared_memory.SharedMemory(name=shm_name)
        buffer = np.ndarray((np.prod(shape),), dtype=dtype, buffer=shm.buf)
        return cls(buffer=buffer, shm=shm, dtype=dtype, original_shape=shape)

    @staticmethod
    def _ensure_dtype(dtype: Union[np.dtype, type, str]) -> np.dtype:
        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)
        return dtype

    @property
    def name(self) -> str:
        return self.shm.name

    @property
    def size(self) -> int:
        return self.shm.size

    def copy_into_buffer(self, array: np.ndarray):
        if array.dtype != self.dtype:
            raise ValueError(f"Array dtype {array.dtype} does not match SharedMemoryElement dtype {self.dtype}")
        flat_array = array.ravel()
        np.copyto(dst=self.buffer, src=flat_array)

    def copy_from_buffer(self) -> np.ndarray:
        return np.copy(self.buffer).reshape(self.original_shape)

    def reshape(self, new_shape: Tuple[int, ...]):
        if np.prod(new_shape) != np.prod(self.original_shape):
            raise ValueError("New shape must have the same number of elements as the original shape.")
        self.original_shape = new_shape

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()