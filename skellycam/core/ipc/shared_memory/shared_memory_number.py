import multiprocessing

import numpy as np
from pydantic import BaseModel

from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement


class SharedMemoryNumber(BaseModel):
    shm_element: SharedMemoryElement
    shm_valid_flag: multiprocessing.Value = multiprocessing.Value("b", True)
    original: bool = False  # Indicates if this is the original element or a recreated one

    @classmethod
    def create(cls, initial_value: int = -1):
        element = SharedMemoryElement.create(shape=(1,), dtype=np.int64)
        element.buffer[0] = initial_value
        return cls(shm_element=element,
                   original=True)

    @classmethod
    def recreate(cls, shm_name: str):
        element = SharedMemoryElement.recreate(shm_name=shm_name, shape=(1,), dtype=np.int64)
        return cls(shm_element=element)

    @property
    def name(self) -> str:
        return self.shm_element.name

    @property
    def value(self) -> int:
        return int(self.shm_element.buffer[0].copy())

    @value.setter
    def value(self, value: int):
        self.shm_element.buffer[0] = value

    @property
    def valid(self):
        return self.shm_valid_flag.value


    def set(self, value: int) -> None:
        """Set the value of the counter."""
        self.shm_element.buffer[0] = value

    def get(self) -> int:
        """Get the current value of the counter."""
        return int(self.shm_element.buffer[0].copy())

    def close(self) -> None:
        """Close the shared memory."""
        self.shm_element.close()

    def unlink(self) -> None:
        """Unlink the shared memory."""
        if not self.original:
            raise RuntimeError("Cannot unlink from a recreated SharedMemoryNumber, must unlink the original.")
        self.shm_valid_flag.value = False
        self.shm_element.unlink()
