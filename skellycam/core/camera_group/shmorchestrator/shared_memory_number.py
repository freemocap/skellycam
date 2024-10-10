import numpy as np
from pydantic import BaseModel

from skellycam.core.camera_group.shmorchestrator.shared_memory_element import SharedMemoryElement


class SharedMemoryNumber(BaseModel):

    shm_element: SharedMemoryElement

    @classmethod
    def create(cls):
        element = SharedMemoryElement.create(shape=(1,), dtype=np.int64)
        element.buffer[0] = -1
        return cls(shm_element=element)

    @classmethod
    def recreate(cls, shm_name: str):
        element = SharedMemoryElement.recreate(shm_name=shm_name, shape=(1,), dtype=np.int64)
        return cls(shm_element=element)

    @property
    def name(self) -> str:
        return self.shm_element.name
    def set(self, value: int) -> None:
        """Set the value of the counter."""
        self.shm_element.buffer[0] = value

    def get(self) -> int:
        """Get the current value of the counter."""
        return int(self.shm_element.buffer[0])

    def close(self) -> None:
        """Close the shared memory."""
        self.shm_element.close()

    def unlink(self) -> None:
        """Unlink the shared memory."""
        self.shm_element.unlink()
