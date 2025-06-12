import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement, SharedMemoryElementDTO


class SharedMemoryNumberDTO(BaseModel):
    shm_element_dto: SharedMemoryElementDTO

class SharedMemoryNumber(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    shm_element: SharedMemoryElement
    original: bool = False  # Indicates if this is the original element or a recreated one

    @classmethod
    def create(cls, initial_value: int = -1):
        element = SharedMemoryElement.create(shape=(1,), dtype=np.int64)
        element.buffer[0] = initial_value
        return cls(shm_element=element,
                   original=True)

    @classmethod
    def recreate(cls, dto: SharedMemoryNumberDTO):
        element = SharedMemoryElement.recreate(dto=dto.shm_element_dto)
        return cls(shm_element=element,
                   original=False)

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
        return self.shm_element.valid

    @valid.setter
    def valid(self, value: bool):
        self.shm_element.valid = bool(value)

    def to_dto(self) -> SharedMemoryNumberDTO:
        """Convert the shared memory number to a DTO."""
        return SharedMemoryNumberDTO(
            shm_element_dto=self.shm_element.to_dto()
        )

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
        self.valid = False
        self.shm_element.unlink()
