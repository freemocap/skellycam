import numpy as np

from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement


class SharedMemoryNumber(SharedMemoryElement):

    @classmethod
    def create(cls, read_only: bool, dtype: np.dtype = np.int64, initial_value: int = -1):
        if isinstance(dtype, type):
            # Convert type to dtype if a type was passed
            dtype = np.dtype(dtype)

        # Create a structured dtype with a single field 'value'
        if dtype.names is None:
            dtype = np.dtype([('value', dtype)])

        instance = super().create(dtype=dtype, read_only=read_only)
        # Assign the value to the 'value' field of the record
        instance.value = initial_value
        return instance

    @property
    def value(self) -> int:
        # Extract the value from the 'value' field of the record
        return int(self.retrieve_data().value)

    @value.setter
    def value(self, value: int):
        # Create a structured array with a single field 'value' and shape (1,)
        data = np.recarray(shape=(1,), dtype=self.dtype)
        data.value = value
        self.put_data(data)

if __name__ == "__main__":
    print("Creating original SharedMemoryNumber...")
    original = SharedMemoryNumber.create(initial_value=42, read_only=False)

    print(f"Original value: {original.value}")

    # Create DTO for sharing with another process
    dto = original.to_dto()
    print(f"DTO: {dto}")

    # Simulate another process by recreating from DTO
    print("Recreating from DTO (simulating another process)...")
    copy = SharedMemoryNumber.recreate(dto=dto, read_only=True)

    # Get value from the copy
    retrieved_value = copy.value
    print(f"Retrieved value: {retrieved_value}")

    # Verify value is the same
    is_equal = original.value == retrieved_value
    print(f"Value verification: {'Success' if is_equal else 'Failed'}")

    # Test modifying the value
    print("Modifying value...")
    original.value = 100
    print(f"Original after modification: {original.value}")
    print(f"Copy after original was modified: {copy.value}")

    # Test valid flag
    print(f"Valid flag: {copy.valid}")
    original.valid = False
    print(f"Valid flag after setting to False: {copy.valid}")

    # Clean up
    print("Cleaning up...")
    copy.close()
    print("Closed copy.")

    # Clean up original
    original.unlink_and_close()
    print("Closed and unlinked original.")

    print("Test completed.")