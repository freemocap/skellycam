import gc
import time
from multiprocessing import Process
import os
import sys
import pytest
import numpy as np
import psutil

from skellycam.core.ipc.shared_memory.shared_memory_element import (
    SharedMemoryElement,
    SharedMemoryElementDTO
)


# Define process functions at module level so they can be pickled
def reader_process_func(dto_dict, iterations):
    """Reader process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryElementDTO(**dto_dict)

    # Recreate element
    element = SharedMemoryElement.recreate(dto, read_only=True)

    # Read in a loop
    for _ in range(iterations):
        data = element.retrieve_data()
        if data is not None:
            # Just read, don't modify
            pass
        time.sleep(0.01)

    # Clean up
    element.close()


def writer_process_func(dto_dict, iterations):
    """Writer process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryElementDTO(**dto_dict)

    # Recreate element
    element = SharedMemoryElement.recreate(dto, read_only=False)

    # Write in a loop
    for i in range(iterations):
        data = np.rec.array((float(i), float(i * 2), float(i * 3)),
                            dtype=np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)]))
        element.put_data(data)
        time.sleep(0.02)

    # Clean up
    element.close()


def child_process_func(dto_dict):
    """Child process function for interprocess communication test."""
    # Convert dict back to DTO
    dto = SharedMemoryElementDTO(**dto_dict)

    # Recreate element
    element = SharedMemoryElement.recreate(dto, read_only=False)

    # Wait for data
    max_attempts = 10
    for _ in range(max_attempts):
        data = element.retrieve_data()
        if data is not None:
            break
        time.sleep(0.1)

    # Modify data
    if data is not None:
        new_data = np.rec.array((data.x * 2, data.y * 2, data.z * 2),
                                dtype=np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)]))
        element.put_data(new_data)

    # Clean up
    element.close()


class TestSharedMemoryElement:
    """Tests for the SharedMemoryElement class."""

    @pytest.fixture
    def simple_dtype(self):
        """Return a simple dtype for testing."""
        return np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)])

    @pytest.fixture
    def large_dtype(self):
        """Return a large dtype for memory leak testing."""
        return np.dtype([('large_array', np.float64, (100, 100))])  # Reduced size for faster tests

    @pytest.fixture
    def simple_element(self, simple_dtype):
        """Create and return a SharedMemoryElement with simple dtype."""
        element = SharedMemoryElement.create(dtype=simple_dtype, read_only=False)
        yield element
        # Cleanup
        if element.valid:
            try:
                element.unlink_and_close()
            except Exception:
                pass

    @pytest.fixture
    def large_element(self, large_dtype):
        """Create and return a SharedMemoryElement with large dtype."""
        element = SharedMemoryElement.create(dtype=large_dtype, read_only=False)
        yield element
        # Cleanup
        if element.valid:
            try:
                element.unlink_and_close()
            except Exception:
                pass

    def test_create_and_recreate(self, simple_dtype):
        """Test creating and recreating a SharedMemoryElement."""
        # Create original element
        original = SharedMemoryElement.create(dtype=simple_dtype, read_only=False)

        # Create DTO
        dto = original.to_dto()

        # Recreate from DTO
        copy = SharedMemoryElement.recreate(dto, read_only=False)

        # Verify properties
        assert original.dtype == copy.dtype
        assert original.name == copy.name
        assert original.valid == copy.valid
        assert original.first_data_written == copy.first_data_written

        # Clean up
        copy.close()
        original.unlink_and_close()

    def test_put_and_retrieve_data(self, simple_element, simple_dtype):
        """Test putting and retrieving data."""
        # Create test data
        test_data = np.rec.array((2.0, 3.0, 4.0), dtype=simple_dtype)

        # Put data into shared memory
        simple_element.put_data(test_data)

        # Verify first_data_written flag is set
        assert simple_element.first_data_written is True

        # Retrieve data
        retrieved_data = simple_element.retrieve_data()

        # Verify data is not None
        assert retrieved_data is not None

        # Verify data - use structured array comparison
        assert retrieved_data.x == test_data.x
        assert retrieved_data.y == test_data.y
        assert retrieved_data.z == test_data.z

    def test_retrieve_before_first_write(self, simple_element):
        """Test retrieving data before first write."""
        # Should return None
        assert simple_element.retrieve_data() is None
        assert simple_element.first_data_written is False

    def test_valid_flag(self, simple_element):
        """Test valid flag functionality."""
        assert simple_element.valid is True

        # Set valid to False
        simple_element.valid = False
        assert simple_element.valid is False

        # Set valid to True again
        simple_element.valid = True
        assert simple_element.valid is True

    def test_retrieve_invalid_element(self, simple_element):
        """Test retrieving data from an invalid element."""
        simple_element.valid = False

        with pytest.raises(ValueError, match="Cannot retrieve data from an invalid SharedMemoryElement"):
            simple_element.retrieve_data()

    def test_unlink_non_original(self, simple_dtype):
        """Test unlinking a non-original SharedMemoryElement."""
        original = SharedMemoryElement.create(dtype=simple_dtype, read_only=False)
        dto = original.to_dto()
        copy = SharedMemoryElement.recreate(dto, read_only=False)

        with pytest.raises(ValueError, match="Cannot unlink a non-original SharedMemoryElement"):
            copy.unlink()

        # Clean up
        copy.close()
        original.unlink_and_close()

    def test_dtype_mismatch(self, simple_element, simple_dtype):
        """Test putting data with mismatched dtype."""
        wrong_dtype = np.dtype([('a', np.int32), ('b', np.int32)])
        wrong_data = np.rec.array((1, 2), dtype=wrong_dtype)

        with pytest.raises(ValueError, match="Array dtype .* does not match SharedMemoryElement dtype"):
            simple_element.put_data(wrong_data)

    def test_shape_mismatch(self, simple_element, simple_dtype):
        """Test putting data with mismatched shape."""
        # Create array with multiple records
        wrong_shape_data = np.rec.array([(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)], dtype=simple_dtype)

        with pytest.raises(ValueError, match="Array shape .* does not match SharedMemoryElement shape"):
            simple_element.put_data(wrong_shape_data)

    def test_interprocess_communication(self, simple_dtype):
        """Test communication between processes using SharedMemoryElement."""
        # Create original element
        original = SharedMemoryElement.create(dtype=simple_dtype, read_only=False)

        # Put initial data
        initial_data = np.rec.array((1.0, 2.0, 3.0), dtype=simple_dtype)
        original.put_data(initial_data)

        # Verify first_data_written flag is set
        assert original.first_data_written is True

        # Create DTO and convert to dict for passing to child process
        dto = original.to_dto()
        dto_dict = dto.model_dump()

        # Start child process
        process = Process(target=child_process_func, args=(dto_dict,))
        process.start()
        process.join(timeout=5)

        # Wait a bit to ensure data is written back
        time.sleep(0.5)

        # Retrieve modified data
        modified_data = original.retrieve_data()

        # Verify data is not None
        assert modified_data is not None, "Retrieved data is None, first_data_written flag may not be properly shared"

        # Verify data was modified
        assert modified_data.x == 2.0
        assert modified_data.y == 4.0
        assert modified_data.z == 6.0

        # Clean up
        original.unlink_and_close()

    def test_memory_leak_large_data(self, large_dtype):
        """Test for memory leaks when handling large data."""
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large data
        large_data = np.rec.array(np.zeros((1,), dtype=large_dtype))

        # Number of iterations
        iterations = 5  # Reduced for faster tests

        # Create and destroy elements in a loop
        for i in range(iterations):
            element = SharedMemoryElement.create(dtype=large_dtype, read_only=False)
            element.put_data(large_data)

            # Verify first_data_written flag is set
            assert element.first_data_written is True

            retrieved = element.retrieve_data()
            assert retrieved is not None
            element.unlink_and_close()

            # Force garbage collection
            gc.collect()

        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        # Log memory usage for debugging
        print(f"Memory before: {initial_memory:.2f} MB, after: {final_memory:.2f} MB, growth: {memory_growth:.2f} MB")

        # Allow for some memory growth, but not excessive
        # This is a heuristic check - the exact threshold depends on the system
        assert memory_growth < 200, f"Excessive memory growth: {memory_growth} MB"

    def test_memory_leak_multiple_copies(self, large_dtype):
        """Test for memory leaks when creating multiple copies of an element."""
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create original element
        original = SharedMemoryElement.create(dtype=large_dtype, read_only=False)

        # Put data
        large_data = np.rec.array(np.zeros((1,), dtype=large_dtype))
        original.put_data(large_data)

        # Verify first_data_written flag is set
        assert original.first_data_written is True

        # Create DTO
        dto = original.to_dto()

        # Number of iterations
        iterations = 5  # Reduced for faster tests

        # Create and destroy copies in a loop
        copies = []
        for i in range(iterations):
            copy = SharedMemoryElement.recreate(dto, read_only=False)
            retrieved = copy.retrieve_data()
            assert retrieved is not None
            copies.append(copy)

        # Close all copies
        for copy in copies:
            copy.close()

        # Clean up original
        original.unlink_and_close()

        # Force garbage collection
        gc.collect()

        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        # Log memory usage for debugging
        print(f"Memory before: {initial_memory:.2f} MB, after: {final_memory:.2f} MB, growth: {memory_growth:.2f} MB")

        # Allow for some memory growth, but not excessive
        assert memory_growth < 200, f"Excessive memory growth: {memory_growth} MB"

    def test_concurrent_access(self, simple_dtype):
        """Test concurrent access to shared memory from multiple processes."""
        # Create original element
        original = SharedMemoryElement.create(dtype=simple_dtype, read_only=False)

        # Put initial data
        initial_data = np.rec.array((0.0, 0.0, 0.0), dtype=simple_dtype)
        original.put_data(initial_data)

        # Verify first_data_written flag is set
        assert original.first_data_written is True

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