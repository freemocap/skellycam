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
    def create(cls, shape: Tuple[int, ...], dtype: np.dtype):
        dtype = cls._ensure_dtype(dtype)
        payload_size_bytes = int(np.prod(shape, dtype=np.int64) * dtype.itemsize)
        if payload_size_bytes < 0:
            raise ValueError(f"Payload size is negative: {payload_size_bytes}")
        shm = shared_memory.SharedMemory(size=payload_size_bytes, create=True)
        buffer = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        return cls(buffer=buffer, shm=shm, dtype=dtype, original_shape=shape)

    @classmethod
    def recreate(cls, shm_name: str, shape: tuple, dtype: np.dtype):
        dtype = cls._ensure_dtype(dtype)
        shm = shared_memory.SharedMemory(name=shm_name)
        buffer = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
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

    def put_data(self, data: np.ndarray):
        if data.dtype != self.dtype:
            raise ValueError(f"Array dtype {data.dtype} does not match SharedMemoryElement dtype {self.dtype}")
        if data.shape != self.original_shape:
            raise ValueError(f"Array shape {data.shape} does not match SharedMemoryElement shape {self.original_shape}")
        np.copyto(dst=self.buffer, src=data)

    def get_data(self) -> np.ndarray:
        array = np.copy(self.buffer)
        if array.dtype != self.dtype:
            raise ValueError(f"Array dtype {array.dtype} does not match SharedMemoryElement dtype {self.dtype}")
        if array.shape != self.original_shape:
            raise ValueError(f"Array shape {array.shape} does not match SharedMemoryElement shape {self.original_shape}")
        return array


    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()