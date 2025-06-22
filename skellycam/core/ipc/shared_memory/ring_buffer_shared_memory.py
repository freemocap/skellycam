import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement, SharedMemoryElementDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber

ONE_GIGABYTE = 1024 ** 3

import logging
logger = logging.getLogger(__name__)
class SharedMemoryRingBufferDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    shm_dtos: list[SharedMemoryElementDTO]
    last_written_index_shm_dto: SharedMemoryElementDTO
    last_read_index_shm_dto: SharedMemoryElementDTO
    dtype: np.dtype


class SharedMemoryRingBuffer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    shms: list[SharedMemoryElement]
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
        shms = [SharedMemoryElement.create(dtype=example_data.dtype,
                                                  read_only=read_only) for index in range(int(ring_buffer_length))]
        return cls(shms=shms,
                   last_written_index=SharedMemoryNumber.create(initial_value=-1,
                                                                read_only=read_only),
                   last_read_index=SharedMemoryNumber.create(initial_value=-1,
                                                             read_only=read_only),
                   dtype=example_data.dtype,
                   read_only=read_only)

    @property
    def original(self) -> bool:
        return all([all([shm.original for shm in self.shms]),
                    self.last_written_index.original,
                    self.last_read_index.original])

    @property
    def valid(self) -> bool:
        return all([all([shm.valid for shm in self.shms]),
                    self.last_written_index.valid,
                    self.last_read_index.valid])

    @valid.setter
    def valid(self, value: bool):
        for shm in self.shms:
            shm.valid = value
        self.last_written_index.valid = value
        self.last_read_index.valid = value

    @classmethod
    def recreate(cls,
                 dto: SharedMemoryRingBufferDTO,
                 read_only: bool):

        return cls(shms=[SharedMemoryElement.recreate(dto=dto, read_only=read_only) for dto in
                         dto.shm_dtos],
                   last_written_index=SharedMemoryNumber.recreate(dto=dto.last_written_index_shm_dto,
                                                                  read_only=read_only),
                   last_read_index=SharedMemoryNumber.recreate(dto=dto.last_read_index_shm_dto, read_only=read_only),
                   dtype=dto.dtype,
                   read_only=read_only,
                   )

    def to_dto(self) -> SharedMemoryRingBufferDTO:
        return SharedMemoryRingBufferDTO(
            shm_dtos=[shm.to_dto() for shm in self.shms],
            last_written_index_shm_dto=self.last_written_index.to_dto(),
            last_read_index_shm_dto=self.last_read_index.to_dto(),
            dtype=self.dtype,
        )

    @property
    def first_data_written(self) -> bool:
        return self.last_written_index.value != -1

    @property
    def ring_buffer_length(self) -> int:
        return len(self.shms)

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

        self.shms[index_to_write % self.ring_buffer_length].put_data(data)
        self.last_written_index.value = index_to_write

    def get_next_data(self, rec_array:np.recarray|None) -> np.recarray:
        if self.read_only:
            raise ValueError(
                "Cannot call `get_next_data` on read-only SharedMemoryRingBuffer. Use `get_latest_data` instead.")
        if not self.first_data_written:
            raise ValueError("Ring buffer is not ready to read yet.")
        if not self.new_data_available:
            raise ValueError("No new data available to read.")
        return self._read_next_data(rec_array)

    def _read_next_data(self, rec_array:np.recarray|None) -> np.recarray | None:
        if self.last_written_index.value == -1:
            raise ValueError("No data available to read.")
        index_to_read = self.last_read_index.value + 1
        if index_to_read > self.last_written_index.value:
            raise ValueError("Cannot read past the last written index!")
        rec_array = self.shms[index_to_read % self.ring_buffer_length].retrieve_data(rec_array)
        self.last_read_index.value = index_to_read

        return rec_array

    def get_latest_data(self,rec_array:np.recarray|None=None) -> np.recarray:
        """
        NOTE - this method does NOT update the 'last_read_index' value.

        'Get Latest ...'  is intended to get the most up-to-date data (e.g. to keep the images displayed on the screen up-to-date)

        The task of making sure we get ALL the data without overwriting to the 'get_next_data' method (e.g. for making sure we save all the frames to disk/video).
        """
        if self.last_written_index.value == -1:
            raise ValueError("No data available to read.")
        return self.shms[self.last_written_index.value % self.ring_buffer_length].retrieve_data(rec_array)

    def close(self):
        self.last_written_index.close()
        self.last_read_index.close()
        for shm in self.shms:
            shm.close()

    def unlink(self):
        if not self.original:
            raise ValueError("Cannot unlink a non-original SharedMemoryRingBuffer")
        self.valid = False
        self.last_written_index.unlink()
        self.last_read_index.unlink()
        for shm in self.shms:
            shm.unlink()

    def close_and_unlink(self):
        self.unlink()
        self.close()

