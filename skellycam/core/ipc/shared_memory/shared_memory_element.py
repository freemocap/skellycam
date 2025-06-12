from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Tuple, Union, Any

import numpy as np
from pydantic import BaseModel, ConfigDict


class SharedMemoryElementDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    shm_name: str
    shm_valid_name: str
    shape: Tuple[int, ...]
    dtype: np.dtype
    original_shape: Tuple[int, ...]


class SharedMemoryElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    buffer: np.ndarray
    dtype: np.dtype
    shm: shared_memory.SharedMemory
    original_shape: Tuple[int, ...]
    valid_flag_shm: shared_memory.SharedMemory
    valid_flag_buffer: np.ndarray
    original: bool = False

    @classmethod
    def create(cls, shape: Tuple[int, ...], dtype: np.dtype):
        dtype = cls._ensure_dtype(dtype)
        payload_size_bytes = int(np.prod(shape, dtype=np.int64) * dtype.itemsize)
        if payload_size_bytes < 0:
            raise ValueError(f"Payload size is negative: {payload_size_bytes}")
        shm = shared_memory.SharedMemory(size=payload_size_bytes, create=True)
        buffer = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        valid_flag_shm = shared_memory.SharedMemory(size=np.dtype(np.int64).itemsize, create=True)
        valid_flag_buffer = np.ndarray((1,), dtype=np.int64, buffer=valid_flag_shm.buf)
        valid_flag_buffer[0] = 1  # Set valid flag to True (1)
        return cls(buffer=buffer,
                   shm=shm,
                   dtype=dtype,
                   original_shape=shape,
                   valid_flag_shm=valid_flag_shm,
                   valid_flag_buffer=valid_flag_buffer,
                   original=True)

    @classmethod
    def recreate(cls, dto: SharedMemoryElementDTO):
        dtype = cls._ensure_dtype(dto.dtype)
        shm = shared_memory.SharedMemory(name=dto.shm_name)
        buffer = np.ndarray(dto.shape, dtype=dtype, buffer=shm.buf)
        valid_flag_shm = shared_memory.SharedMemory(name=dto.shm_valid_name)
        valid_flag_buffer = np.ndarray((1,), dtype=dtype, buffer=valid_flag_shm.buf)
        return cls(buffer=buffer,
                   shm=shm,
                   dtype=dto.dtype,
                   original_shape=dto.shape,
                   valid_flag_shm=valid_flag_shm,
                   valid_flag_buffer=valid_flag_buffer,
                   original=False)

    @property
    def valid(self) -> bool:
        return bool(np.copy(self.valid_flag_buffer))

    @valid.setter
    def valid(self, value:Any):
         self.valid_flag_buffer[0] = 1 if value else 0

    def to_dto(self) -> SharedMemoryElementDTO:
        return SharedMemoryElementDTO(
            shm_name=self.shm.name,
            shape=self.buffer.shape,
            dtype=self.dtype,
            original_shape=self.original_shape,
            shm_valid_name=self.valid_flag_shm.name
        )

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
            raise ValueError(
                f"Array shape {array.shape} does not match SharedMemoryElement shape {self.original_shape}")
        return array

    def close(self):
        self.shm.close()

    def unlink(self):
        if not self.original:
            raise ValueError(
                "Cannot unlink a non-original SharedMemoryElement, close children and unlink the original.")
        self.valid = False
        self.shm.unlink()
