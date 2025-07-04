import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement, SharedMemoryElementDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber

ONE_KILOBYTE = 1024
ONE_MEGABYTE = 1024 ** 2
ONE_GIGABYTE = 1024 ** 3

import logging

logger = logging.getLogger(__name__)


class SharedMemoryRingBufferDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    ring_shm_dto: SharedMemoryElementDTO
    last_written_index_shm_dto: SharedMemoryElementDTO
    last_read_index_shm_dto: SharedMemoryElementDTO
    dtype: np.dtype


class SharedMemoryRingBuffer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    ring_shm: SharedMemoryElement
    dtype: np.dtype
    last_written_index: SharedMemoryNumber = Field(
        ...,
        description="Allows writing new data in 'put_data' - Represents APPARENT index of last written element from the User's perspective; internally handles wrapping around the array"
    )
    last_read_index: SharedMemoryNumber = Field(
        ...,
        description="Allows incrementing 'read' index in 'read_next` - Represents APPARENT index of last read element from the User's perspective; internally handles wrapping around the array"
    )
    read_only: bool

    @classmethod
    def create(cls,
               example_data: np.recarray,
               read_only: bool,
               memory_allocation: int = ONE_GIGABYTE,
               ring_buffer_length: int = None,
               ):
        if ring_buffer_length is None:
            ring_buffer_length = memory_allocation // example_data.itemsize
        ring_shm = SharedMemoryElement.create(dtype=example_data.dtype,
                                              read_only=read_only,
                                              buffer_shape=(ring_buffer_length,))
        return cls(ring_shm=ring_shm,
                   last_written_index=SharedMemoryNumber.create(initial_value=-1,
                                                                read_only=read_only),
                   last_read_index=SharedMemoryNumber.create(initial_value=-1,
                                                             read_only=read_only),
                   dtype=example_data.dtype,
                   read_only=read_only)

    @property
    def original(self) -> bool:
        return all([self.ring_shm.original,
                    self.last_written_index.original,
                    self.last_read_index.original])

    @property
    def valid(self) -> bool:
        return all([self.ring_shm.valid,
                    self.last_written_index.valid,
                    self.last_read_index.valid])

    @valid.setter
    def valid(self, value: bool):
        self.ring_shm.valid = value
        self.last_written_index.valid = value
        self.last_read_index.valid = value

    @classmethod
    def recreate(cls,
                 dto: SharedMemoryRingBufferDTO,
                 read_only: bool):

        return cls(ring_shm=SharedMemoryElement.recreate(dto=dto.ring_shm_dto, read_only=read_only),
                   last_written_index=SharedMemoryNumber.recreate(dto=dto.last_written_index_shm_dto,
                                                                  read_only=read_only),
                   last_read_index=SharedMemoryNumber.recreate(dto=dto.last_read_index_shm_dto, read_only=read_only),
                   dtype=dto.dtype,
                   read_only=read_only,
                   )

    def to_dto(self) -> SharedMemoryRingBufferDTO:
        return SharedMemoryRingBufferDTO(
            ring_shm_dto=self.ring_shm.to_dto(),
            last_written_index_shm_dto=self.last_written_index.to_dto(),
            last_read_index_shm_dto=self.last_read_index.to_dto(),
            dtype=self.dtype,
        )

    @property
    def first_data_written(self) -> bool:
        return self.last_written_index.value != -1

    @property
    def ring_buffer_length(self) -> int:
        return self.ring_shm.buffer.shape[0]

    @property
    def new_data_available(self) -> bool:
        return self.first_data_written and self.last_written_index.value > self.last_read_index.value

    @property
    def new_data_indicies(self) -> list[int]:
        if not self.first_data_written:
            return []
        if not self.new_data_available:
            return []
        return list(range(self.last_read_index.value, self.last_written_index.value))

    def _check_for_overwrite(self, next_index: int) -> bool:
        return next_index % self.ring_buffer_length == self.last_read_index.value % self.ring_buffer_length

    def put_data(self, data: np.recarray, overwrite: bool = False):
        if self.read_only:
            raise ValueError("Cannot write to read-only SharedMemoryRingBuffer.")
        if data.dtype != self.dtype:
            raise ValueError(f"Data type {data.dtype} does not match SharedMemoryRingBuffer data type {self.dtype}.")

        index_to_write = self.last_written_index.value + 1
        if self._check_for_overwrite(index_to_write) and not overwrite and False:
            raise ValueError("Cannot overwrite data that hasn't been read yet.")

        self.ring_shm.buffer[index_to_write % self.ring_buffer_length] = data
        self.last_written_index.value = index_to_write

    def get_next_data(self, rec_array: np.recarray | None) -> np.recarray:
        if self.read_only:
            raise ValueError(
                "Cannot call `get_next_data` on read-only SharedMemoryRingBuffer. Use `get_latest_data` instead.")
        if not self.first_data_written:
            raise ValueError("Ring buffer is not ready to read yet.")
        if not self.new_data_available:
            raise ValueError("No new data available to read.")
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return self._read_next_data(rec_array)

    def _read_next_data(self, rec_array: np.recarray | None) -> np.recarray | None:
        if self.last_written_index.value == -1:
            raise ValueError("No data available to read.")
        index_to_read = self.last_read_index.value + 1
        if index_to_read > self.last_written_index.value:
            raise ValueError("Cannot read past the last written index!")
        if rec_array is None:
            rec_array = np.recarray(1, dtype=self.dtype)
        np.copyto(rec_array,self.ring_shm.buffer[index_to_read % self.ring_buffer_length])
        self.last_read_index.value = index_to_read

        return rec_array

    def get_latest_data(self, rec_array: np.recarray | None = None) -> np.recarray:
        """
        NOTE - this method does NOT update the 'last_read_index' value.

        'Get Latest ...'  is intended to get the most up-to-date data (e.g. to keep the images displayed on the screen up-to-date)

        The task of making sure we get ALL the data without overwriting to the 'get_next_data' method (e.g. for making sure we save all the frames to disk/video).
        """
        if self.last_written_index.value == -1:
            raise ValueError("No data available to read.")
        if rec_array is None:
            rec_array = np.recarray(1, dtype=self.dtype)
        np.copyto(rec_array,self.ring_shm.buffer[self.last_written_index.value % self.ring_buffer_length])
        return rec_array

    def close(self):
        self.last_written_index.close()
        self.last_read_index.close()
        self.ring_shm.close()

    def unlink(self):
        if not self.original:
            raise ValueError("Cannot unlink a non-original SharedMemoryRingBuffer")
        self.valid = False
        self.last_written_index.unlink()
        self.last_read_index.unlink()
        self.ring_shm.unlink()

    def close_and_unlink(self):
        self.unlink()
        self.close()


if __name__ == "__main__":
    print("Testing SharedMemoryRingBuffer...")

    # Define a custom dtype for testing
    test_dtype = np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)])

    # Create example payload
    _example_data = np.recarray((1,), dtype=test_dtype)

    print("Creating original SharedMemoryRingBuffer...")
    # Create a small ring buffer for testing with just 5 slots
    original = SharedMemoryRingBuffer.create(
        example_data=_example_data,
        read_only=False,
        ring_buffer_length=5
    )

    print(f"Ring buffer length: {original.ring_buffer_length}")
    print(f"First frame written: {original.first_data_written}")

    # Create test data
    test_data1 = np.rec.array([(1.0, 2.0, 3.0)], dtype=test_dtype)
    test_data2 = np.rec.array([(4.0, 5.0, 6.0)], dtype=test_dtype)
    test_data3 = np.rec.array([(7.0, 8.0, 9.0)], dtype=test_dtype)

    # Put data into the ring buffer
    print("Writing data to ring buffer...")
    original.put_data(test_data1)
    print(f"Last written index after first write: {original.last_written_index.value}")
    original.put_data(test_data2)
    print(f"Last written index after second write: {original.last_written_index.value}")
    original.put_data(test_data3)
    print(f"Last written index after third write: {original.last_written_index.value}")

    # Create DTO for sharing with another process
    _dto = original.to_dto()
    print(f"Created DTO: {repr(_dto)}")

    # Simulate another process by recreating from DTO
    print("Recreating from DTO (simulating another process)...")
    _copy = SharedMemoryRingBuffer.recreate(dto=_dto, read_only=True)

    # Get latest data from the _copy
    print("Reading latest data...")
    latest_data = _copy.get_latest_data()
    print(f"Latest data: {latest_data}")

    # Create a reader that consumes data sequentially
    reader = SharedMemoryRingBuffer.recreate(dto=_dto, read_only=False)

    print("Reading data sequentially...")
    # Read all available data
    while reader.new_data_available:
        data = reader.get_next_data(
            rec_array=np.recarray(1, dtype=test_dtype)  # Create a new recarray for reading
        )
        print(f"Read data: {data}")

    # Write more data to test wrapping
    print("\nTesting buffer wrapping...")
    for i in range(6):  # Write more than buffer size to test wrapping
        test_data = np.rec.array([(i * 10.0, i * 10.0 + 1, i * 10.0 + 2)], dtype=test_dtype)
        original.put_data(test_data, overwrite=True)
        print(f"Wrote data {i}: {test_data}")


    while reader.new_data_available:
        data = reader.get_next_data(
            rec_array=None # test non-allocating read
        )
        print(f"Read data: {data}")

    for i in range(6):  # Write more than buffer size to test wrapping
        test_data = np.rec.array([(i * 10.0, i * 10.0 + 1, i * 10.0 + 2)], dtype=test_dtype)
        original.put_data(test_data, overwrite=True)
        print(f"Wrote data {i}: {test_data}")

    print("\nReading latest data after wrapping...")
    latest_data = _copy.get_latest_data()
    print(f"Latest data: {latest_data}")

    # Test valid flag
    print(f"\nValid flag: {_copy.valid}")
    original.valid = False
    print(f"Valid flag after setting to False: {_copy.valid}")

    # Clean up
    print("\nCleaning up...")
    _copy.close()
    reader.close()
    print("Closed copies.")

    # Clean up original
    original.close_and_unlink()
    print("Closed and unlinked original.")

    print("Test completed.")
