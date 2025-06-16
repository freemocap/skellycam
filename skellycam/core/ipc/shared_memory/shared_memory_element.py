from multiprocessing import shared_memory
from typing import Any

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel, ConfigDict

from skellycam.core.types.type_overloads import SharedMemoryName


class SharedMemoryElementDTO(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )
    shm_name: str
    shm_valid_name: str
    dtype: np.dtype



class SharedMemoryElement(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )
    buffer: np.recarray
    valid_flag_buffer: NDArray[Shape["1"], np.bool_]
    dtype: np.dtype
    shm: shared_memory.SharedMemory
    valid_flag_shm: shared_memory.SharedMemory
    original: bool = False

    @classmethod
    def create(cls, dtype: np.dtype):

        shm = shared_memory.SharedMemory(size=dtype.itemsize, create=True)
        buffer = np.recarray(shape=(1,), dtype=dtype, buf=shm.buf)
        valid_flag_shm = shared_memory.SharedMemory(size=np.dtype(np.bool_).itemsize, create=True)
        valid_flag_buffer = np.ndarray((1,), dtype=np.bool_, buffer=valid_flag_shm.buf)
        valid_flag_buffer[0] = True
        return cls(
            buffer=buffer,
            shm=shm,
                   dtype=dtype,
                   valid_flag_shm=valid_flag_shm,
                   valid_flag_buffer=valid_flag_buffer,
            original=True
        )

    @classmethod
    def recreate(cls, dto: SharedMemoryElementDTO):
        shm = shared_memory.SharedMemory(name=dto.shm_name)
        buffer = np.recarray(shape=(1,), dtype=dto.dtype, buf=shm.buf)
        valid_flag_shm = shared_memory.SharedMemory(name=dto.shm_valid_name)
        valid_flag_buffer = np.ndarray((1,), dtype=np.bool_, buffer=valid_flag_shm.buf)
        return cls(
            buffer=buffer,
            shm=shm,
            dtype=dto.dtype,
            valid_flag_shm=valid_flag_shm,
            valid_flag_buffer=valid_flag_buffer,
            original=False
        )

    @property
    def valid(self) -> bool:
        return bool(np.copy(self.valid_flag_buffer)[0])

    @valid.setter
    def valid(self, value: Any):
        self.valid_flag_buffer[0] = bool(value)
    def to_dto(self) -> SharedMemoryElementDTO:
        return SharedMemoryElementDTO(
            shm_name=self.shm.name,
            dtype=self.dtype,
            shm_valid_name=self.valid_flag_shm.name
        )

    @property
    def name(self) -> SharedMemoryName:
        return self.shm.name

    @property
    def size(self) -> int:
        return self.shm.size

    def put_data(self, data: np.recarray):
        if data.dtype != self.dtype:
            raise ValueError(f"Array dtype {data.dtype} does not match SharedMemoryElement dtype {self.dtype}")

        # Handle scalar records
        if data.shape == () and self.buffer.shape == (1,):
            np.copyto(dst=self.buffer, src=np.array([data], dtype=self.dtype))
            return

        # Handle array records
        if data.shape != self.buffer.shape:
            raise ValueError(
                f"Array shape {data.shape} does not match SharedMemoryElement shape {self.buffer.shape}")

        np.copyto(dst=self.buffer, src=data)

    def get_data(self) -> np.recarray:
        data = np.copy(self.buffer)
        if data.dtype != self.dtype:
            raise ValueError(f"Array dtype {data.dtype} does not match SharedMemoryElement dtype {self.dtype}")

        # For consistency, if we have a single record array, return it as a scalar
        if data.shape == (1,):
            return data[0]
        return data

    def close_and_unlink(self):
        self.unlink()
        self.close()
    def close(self):
        self.shm.close()
        self.valid_flag_shm.close()

    def unlink(self):
        if not self.original:
            raise ValueError(
                "Cannot unlink a non-original SharedMemoryElement, close children and unlink the original.")
        self.valid = False
        self.shm.unlink()
        self.valid_flag_shm.unlink()

if __name__ == "__main__":

    # Define a custom dtype for testing
    test_dtype = np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)])

    print("Creating original SharedMemoryElement...")
    original = SharedMemoryElement.create(dtype=test_dtype)

    # Create test data
    test_data = np.rec.array((2,3,4), dtype=test_dtype)

    print(f"Original data:\n{test_data}")

    # Put data into shared memory
    original.put_data(test_data)

    # Create DTO for sharing with another process
    dto = original.to_dto()
    print(f"DTO: {dto}")

    # Simulate another process by recreating from DTO
    print("Recreating from DTO (simulating another process)...")
    copy = SharedMemoryElement.recreate(dto)

    # Get data from the copy
    retrieved_data = copy.get_data()
    print(f"Retrieved data:\n{retrieved_data}")

    # Verify data is the same
    is_equal = np.array_equal(test_data, retrieved_data)
    print(f"Data verification: {'Success' if is_equal else 'Failed'}")

    # Test valid flag
    print(f"Valid flag: {copy.valid}")
    original.valid = False
    print(f"Valid flag after setting to False: {copy.valid}")

    # Clean up
    print("Cleaning up...")
    copy.close()
    print("Closed copy.")
    # Use the new method for safe cleanup
    original.close_and_unlink()
    print("Closed and unlinked original.")

    print("Test completed.")