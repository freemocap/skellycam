import gc
import time
from multiprocessing import Process
import os
import sys
import pytest
import numpy as np
import psutil

from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber
from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElementDTO


# Define process functions at module level so they can be pickled
def reader_process_func(dto_dict, iterations):
    """Reader process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryElementDTO(**dto_dict)

    # Recreate element
    number = SharedMemoryNumber.recreate(dto, read_only=True)

    # Read in a loop
    for _ in range(iterations):
        value = number.value
        # Just read, don't modify
        time.sleep(0.01)

    # Clean up
    number.close()


def writer_process_func(dto_dict, iterations):
    """Writer process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryElementDTO(**dto_dict)

    # Recreate element
    number = SharedMemoryNumber.recreate(dto, read_only=False)

    # Write in a loop
    for i in range(iterations):
        number.value = i
        time.sleep(0.02)

    # Clean up
    number.close()


def child_process_func(dto_dict):
    """Child process function for interprocess communication test."""
    # Convert dict back to DTO
    dto = SharedMemoryElementDTO(**dto_dict)

    # Recreate element
    number = SharedMemoryNumber.recreate(dto, read_only=False)

    # Wait for data
    max_attempts = 10
    for _ in range(max_attempts):
        try:
            value = number.value
            break
        except Exception:
            time.sleep(0.1)

    # Modify data
    number.value = value * 2

    # Clean up
    number.close()


class TestSharedMemoryNumber:
    """Tests for the SharedMemoryNumber class."""

    @pytest.fixture
    def simple_number(self):
        """Create and return a SharedMemoryNumber."""
        number = SharedMemoryNumber.create(initial_value=42, read_only=False)
        yield number
        # Cleanup
        if number.valid:
            try:
                number.unlink_and_close()
            except Exception:
                pass

    @pytest.fixture
    def zero_number(self):
        """Create and return a SharedMemoryNumber with initial value 0."""
        number = SharedMemoryNumber.create(initial_value=0, read_only=False)
        yield number
        # Cleanup
        if number.valid:
            try:
                number.unlink_and_close()
            except Exception:
                pass

    @pytest.fixture
    def float_number(self):
        """Create and return a SharedMemoryNumber with float dtype."""
        number = SharedMemoryNumber.create(initial_value=3.14, dtype=np.float64, read_only=False)
        yield number
        # Cleanup
        if number.valid:
            try:
                number.unlink_and_close()
            except Exception:
                pass

    def test_create_with_initial_value(self):
        """Test creating a SharedMemoryNumber with an initial value."""
        initial_value = 42
        number = SharedMemoryNumber.create(initial_value=initial_value, read_only=False)
        
        # Verify initial value
        assert number.value == initial_value
        
        # Clean up
        number.unlink_and_close()

    def test_create_with_different_dtypes(self):
        """Test creating SharedMemoryNumber with different dtypes."""
        # Test with int32
        int32_number = SharedMemoryNumber.create(initial_value=42, dtype=np.int32, read_only=False)
        assert int32_number.value == 42
        int32_number.unlink_and_close()
        
        # Test with float64
        float64_number = SharedMemoryNumber.create(initial_value=3.14, dtype=np.float64, read_only=False)
        assert float64_number.value == 3  # Should be converted to int
        float64_number.unlink_and_close()
        
        # Test with uint8
        uint8_number = SharedMemoryNumber.create(initial_value=255, dtype=np.uint8, read_only=False)
        assert uint8_number.value == 255
        uint8_number.unlink_and_close()

    def test_value_property(self, simple_number):
        """Test the value property getter and setter."""
        # Verify initial value
        assert simple_number.value == 42
        
        # Set new value
        simple_number.value = 100
        assert simple_number.value == 100
        
        # Set negative value
        simple_number.value = -10
        assert simple_number.value == -10
        
        # Set zero
        simple_number.value = 0
        assert simple_number.value == 0

    def test_create_and_recreate(self):
        """Test creating and recreating a SharedMemoryNumber."""
        # Create original element
        original = SharedMemoryNumber.create(initial_value=42, read_only=False)

        # Create DTO
        dto = original.to_dto()

        # Recreate from DTO
        copy = SharedMemoryNumber.recreate(dto, read_only=False)

        # Verify properties
        assert original.value == copy.value
        assert original.name == copy.name
        assert original.valid == copy.valid
        assert original.first_data_written == copy.first_data_written

        # Clean up
        copy.close()
        original.unlink_and_close()

    def test_read_only_access(self):
        """Test read-only access to SharedMemoryNumber."""
        # Create original with write access
        original = SharedMemoryNumber.create(initial_value=42, read_only=False)
        
        # Create DTO
        dto = original.to_dto()
        
        # Recreate with read-only access
        read_only_copy = SharedMemoryNumber.recreate(dto, read_only=True)
        
        # Verify value can be read
        assert read_only_copy.value == 42
        
        # Modify original
        original.value = 100
        
        # Verify read-only copy sees the change
        assert read_only_copy.value == 100
        
        # Clean up
        read_only_copy.close()
        original.unlink_and_close()

    def test_interprocess_communication(self):
        """Test communication between processes using SharedMemoryNumber."""
        # Create original element
        original = SharedMemoryNumber.create(initial_value=42, read_only=False)

        # Create DTO and convert to dict for passing to child process
        dto = original.to_dto()
        dto_dict = dto.model_dump()

        # Start child process
        process = Process(target=child_process_func, args=(dto_dict,))
        process.start()
        process.join(timeout=5)

        # Wait a bit to ensure data is written back
        time.sleep(0.5)

        # Retrieve modified value
        modified_value = original.value

        # Verify value was modified
        assert modified_value == 84  # 42 * 2

        # Clean up
        original.unlink_and_close()

    def test_concurrent_access(self):
        """Test concurrent access to shared memory from multiple processes."""
        # Create original element
        original = SharedMemoryNumber.create(initial_value=0, read_only=False)

        # Create DTO and convert to dict for passing to child processes
        dto = original.to_dto()
        dto_dict = dto.model_dump()

        # Number of iterations
        iterations = 20  # Reduced for faster tests

        # Start reader and writer processes
        reader = Process(target=reader_process_func, args=(dto_dict, iterations))
        writer = Process(target=writer_process_func, args=(dto_dict, iterations))

        reader.start()
        writer.start()

        # Wait for processes to complete
        reader.join(timeout=5)
        writer.join(timeout=5)

        # Verify processes completed successfully
        assert not reader.is_alive(), "Reader process did not complete"
        assert not writer.is_alive(), "Writer process did not complete"

        # Clean up
        original.unlink_and_close()

    def test_memory_leak(self):
        """Test for memory leaks when creating and destroying SharedMemoryNumber instances."""
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Number of iterations
        iterations = 100  # Create and destroy many instances

        # Create and destroy elements in a loop
        for i in range(iterations):
            number = SharedMemoryNumber.create(initial_value=i, read_only=False)
            assert number.value == i
            number.unlink_and_close()

            # Force garbage collection
            gc.collect()

        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        # Log memory usage for debugging
        print(f"Memory before: {initial_memory:.2f} MB, after: {final_memory:.2f} MB, growth: {memory_growth:.2f} MB")

        # Allow for some memory growth, but not excessive
        assert memory_growth < 50, f"Excessive memory growth: {memory_growth} MB"

    def test_invalid_number(self, simple_number):
        """Test behavior when the SharedMemoryNumber becomes invalid."""
        # Set valid to False
        simple_number.valid = False
        
        # Attempting to get value should raise an error
        with pytest.raises(ValueError, match="Cannot retrieve data from an invalid SharedMemoryElement"):
            _ = simple_number.value
            
        # Set valid back to True
        simple_number.valid = True
        
        # Now it should work again
        assert simple_number.value == 42

    def test_zero_value(self, zero_number):
        """Test behavior with zero value."""
        assert zero_number.value == 0
        
        # Change to non-zero
        zero_number.value = 100
        assert zero_number.value == 100
        
        # Change back to zero
        zero_number.value = 0
        assert zero_number.value == 0

    def test_large_values(self):
        """Test with large integer values."""
        # Test with a value near the max int64
        large_value = 9223372036854775807  # Max int64
        number = SharedMemoryNumber.create(initial_value=large_value, dtype=np.int64, read_only=False)
        assert number.value == large_value
        number.unlink_and_close()
        
        # Test with a value near the min int64
        min_value = -9223372036854775808  # Min int64
        number = SharedMemoryNumber.create(initial_value=min_value, dtype=np.int64, read_only=False)
        assert number.value == min_value
        number.unlink_and_close()

    def test_float_conversion(self, float_number):
        """Test conversion of float values to int."""
        # The value property should return an int even for float dtypes
        assert isinstance(float_number.value, int)
        assert float_number.value == 3  # 3.14 truncated to int
        
        # Set a new float value
        float_number.value = 7.89
        assert float_number.value == 7  # 7.89 truncated to int