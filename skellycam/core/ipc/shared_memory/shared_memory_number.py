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
        # Create a structured dtype for the integer
        int_dtype = np.dtype([('value', np.int64)])
        element = SharedMemoryElement.create(dtype=int_dtype)
        # Assign the value to the 'value' field of the record
        element.buffer[0]['value'] = initial_value
        return cls(shm_element=element,
                   original=True)

    @property
    def value(self) -> int:
        # Extract the value from the 'value' field of the record
        return int(self.shm_element.buffer[0]['value'].copy())

    @value.setter
    def value(self, value: int):
        self.shm_element.buffer[0]['value'] = value

    def set(self, value: int) -> None:
        """Set the value of the counter."""
        self.shm_element.buffer[0]['value'] = value

    def get(self) -> int:
        """Get the current value of the counter."""
        return int(self.shm_element.buffer[0]['value'].copy())
    @classmethod
    def recreate(cls, dto: SharedMemoryNumberDTO):
        element = SharedMemoryElement.recreate(dto=dto.shm_element_dto)
        return cls(shm_element=element,
                   original=False)

    @property
    def name(self) -> str:
        return self.shm_element.name



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

    def close(self) -> None:
        """Close the shared memory."""
        self.shm_element.close()

    def unlink(self) -> None:
        """Unlink the shared memory."""
        if not self.original:
            raise RuntimeError("Cannot unlink from a recreated SharedMemoryNumber, must unlink the original.")
        self.valid = False
        self.shm_element.unlink()


if __name__ == "__main__":
    print("Creating original SharedMemoryNumber...")
    original = SharedMemoryNumber.create(initial_value=42)

    print(f"Original value: {original.value}")

    # Create DTO for sharing with another process
    dto = original.to_dto()
    print(f"DTO: {dto}")

    # Simulate another process by recreating from DTO
    print("Recreating from DTO (simulating another process)...")
    copy = SharedMemoryNumber.recreate(dto)

    # Get value from the copy
    retrieved_value = copy.get()
    print(f"Retrieved value: {retrieved_value}")

    # Verify value is the same
    is_equal = original.value == retrieved_value
    print(f"Value verification: {'Success' if is_equal else 'Failed'}")

    # Test modifying the value
    print("Modifying value...")
    original.set(100)
    print(f"Original after modification: {original.value}")
    print(f"Copy after original was modified: {copy.get()}")

    # Test valid flag
    print(f"Valid flag: {copy.valid}")
    original.valid = False
    print(f"Valid flag after setting to False: {copy.valid}")

    # Clean up
    print("Cleaning up...")
    copy.close()
    print("Closed copy.")

    # Clean up original
    original.shm_element.close_and_unlink()
    print("Closed and unlinked original.")

    print("Test completed.")