import gc
import time
from multiprocessing import Process
import os
import sys
import pytest
import numpy as np
import psutil

from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import (
    SharedMemoryRingBuffer,
    SharedMemoryRingBufferDTO
)


# Define process functions at module level so they can be pickled
def reader_process_func(dto_dict, iterations):
    """Reader process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryRingBufferDTO(**dto_dict)

    # Recreate ring buffer
    ring_buffer = SharedMemoryRingBuffer.recreate(dto, read_only=True)

    # Read in a loop
    for _ in range(iterations):
        try:
            # Just read latest data, don't modify
            data = ring_buffer.get_latest_data()
        except ValueError:
            # No data available yet
            pass
        time.sleep(0.01)

    # Clean up
    ring_buffer.close()


def sequential_reader_process_func(dto_dict, iterations):
    """Sequential reader process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryRingBufferDTO(**dto_dict)

    # Recreate ring buffer
    ring_buffer = SharedMemoryRingBuffer.recreate(dto, read_only=False)

    # Read in a loop
    read_count = 0
    for _ in range(iterations * 2):  # More iterations to ensure we catch all writes
        try:
            if ring_buffer.new_data_available:
                data = ring_buffer.get_next_data()
                read_count += 1
        except ValueError:
            # No data available yet
            pass
        time.sleep(0.01)

    # Clean up
    ring_buffer.close()
    return read_count


def writer_process_func(dto_dict, iterations):
    """Writer process function for multiprocessing tests."""
    # Convert dict back to DTO
    dto = SharedMemoryRingBufferDTO(**dto_dict)

    # Recreate ring buffer
    ring_buffer = SharedMemoryRingBuffer.recreate(dto, read_only=False)

    # Write in a loop
    for i in range(iterations):
        data = np.rec.array([(float(i), float(i * 2), float(i * 3))],
                            dtype=np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)]))
        ring_buffer.put_data(data)
        time.sleep(0.02)

    # Clean up
    ring_buffer.close()


class TestSharedMemoryRingBuffer:
    """Tests for the SharedMemoryRingBuffer class."""

    @pytest.fixture
    def simple_dtype(self):
        """Return a simple dtype for testing."""
        return np.dtype([('x', np.float64), ('y', np.float64), ('z', np.float64)])

    @pytest.fixture
    def large_dtype(self):
        """Return a large dtype for memory leak testing."""
        return np.dtype([('large_array', np.float64, (50, 50))])  # Reduced size for faster tests

    @pytest.fixture
    def example_data(self, simple_dtype):
        """Create example data for testing."""
        return np.recarray((1,), dtype=simple_dtype)

    @pytest.fixture
    def large_example_data(self, large_dtype):
        """Create large example data for testing."""
        return np.recarray((1,), dtype=large_dtype)

    @pytest.fixture
    def simple_ring_buffer(self, example_data):
        """Create and return a SharedMemoryRingBuffer with simple dtype."""
        ring_buffer = SharedMemoryRingBuffer.create(
            example_data=example_data,
            read_only=False,
            ring_buffer_length=5  # Small buffer for testing
        )
        yield ring_buffer
        # Cleanup
        if ring_buffer.valid:
            try:
                ring_buffer.close_and_unlink()
            except Exception:
                pass

    @pytest.fixture
    def large_ring_buffer(self, large_example_data):
        """Create and return a SharedMemoryRingBuffer with large dtype."""
        ring_buffer = SharedMemoryRingBuffer.create(
            example_data=large_example_data,
            read_only=False,
            ring_buffer_length=3  # Small buffer for testing
        )
        yield ring_buffer
        # Cleanup
        if ring_buffer.valid:
            try:
                ring_buffer.close_and_unlink()
            except Exception:
                pass

    def test_create_and_recreate(self, example_data):
        """Test creating and recreating a SharedMemoryRingBuffer."""
        # Create original ring buffer
        original = SharedMemoryRingBuffer.create(
            example_data=example_data,
            read_only=False,
            ring_buffer_length=5
        )

        # Create DTO
        dto = original.to_dto()

        # Recreate from DTO
        copy = SharedMemoryRingBuffer.recreate(dto, read_only=False)

        # Verify properties
        assert original.dtype == copy.dtype
        assert original.ring_buffer_length == copy.ring_buffer_length
        assert original.valid == copy.valid
        assert original.first_data_written == copy.first_data_written
        assert original.last_written_index.value == copy.last_written_index.value
        assert original.last_read_index.value == copy.last_read_index.value

        # Clean up
        copy.close()
        original.close_and_unlink()

    def test_put_and_get_latest_data(self, simple_ring_buffer, simple_dtype):
        """Test putting and getting latest data."""
        # Create test data
        test_data = np.rec.array([(2.0, 3.0, 4.0)], dtype=simple_dtype)

        # Initially, no data is available
        assert simple_ring_buffer.first_data_written is False
        with pytest.raises(ValueError, match="No data available to read"):
            simple_ring_buffer.get_latest_data()

        # Put data into shared memory
        simple_ring_buffer.put_data(test_data)

        # Verify first_data_written flag is set
        assert simple_ring_buffer.first_data_written is True
        assert simple_ring_buffer.last_written_index.value == 0

        # Get latest data
        latest_data = simple_ring_buffer.get_latest_data()

        # Verify data
        assert latest_data is not None
        assert latest_data.x == test_data.x[0]
        assert latest_data.y == test_data.y[0]
        assert latest_data.z == test_data.z[0]

        # Put more data
        test_data2 = np.rec.array([(5.0, 6.0, 7.0)], dtype=simple_dtype)
        simple_ring_buffer.put_data(test_data2)

        # Verify last_written_index is updated
        assert simple_ring_buffer.last_written_index.value == 1

        # Get latest data again
        latest_data = simple_ring_buffer.get_latest_data()

        # Verify we get the newest data
        assert latest_data is not None
        assert latest_data.x == test_data2.x[0]
        assert latest_data.y == test_data2.y[0]
        assert latest_data.z == test_data2.z[0]

    def test_get_next_data(self, simple_ring_buffer, simple_dtype):
        """Test getting next data sequentially."""
        # Create test data
        test_data1 = np.rec.array([(1.0, 2.0, 3.0)], dtype=simple_dtype)
        test_data2 = np.rec.array([(4.0, 5.0, 6.0)], dtype=simple_dtype)
        test_data3 = np.rec.array([(7.0, 8.0, 9.0)], dtype=simple_dtype)

        # Initially, no data is available
        assert simple_ring_buffer.first_data_written is False
        with pytest.raises(ValueError, match="Ring buffer is not ready to read yet"):
            simple_ring_buffer.get_next_data()

        # Put data into shared memory
        simple_ring_buffer.put_data(test_data1)
        simple_ring_buffer.put_data(test_data2)
        simple_ring_buffer.put_data(test_data3)

        # Verify first_data_written flag is set
        assert simple_ring_buffer.first_data_written is True
        assert simple_ring_buffer.last_written_index.value == 2
        assert simple_ring_buffer.last_read_index.value == -1

        # Get data sequentially
        data1 = simple_ring_buffer.get_next_data()
        assert data1 is not None
        assert data1.x == test_data1.x[0]
        assert simple_ring_buffer.last_read_index.value == 0

        data2 = simple_ring_buffer.get_next_data()
        assert data2 is not None
        assert data2.x == test_data2.x[0]
        assert simple_ring_buffer.last_read_index.value == 1

        data3 = simple_ring_buffer.get_next_data()
        assert data3 is not None
        assert data3.x == test_data3.x[0]
        assert simple_ring_buffer.last_read_index.value == 2

        # No more data available
        with pytest.raises(ValueError, match="No new data available to read"):
            simple_ring_buffer.get_next_data()

    def test_buffer_wrapping(self, simple_ring_buffer, simple_dtype):
        """Test buffer wrapping behavior."""
        # Fill the buffer and then some to test wrapping
        for i in range(10):  # More than buffer size (5)
            test_data = np.rec.array([(float(i), float(i * 2), float(i * 3))], dtype=simple_dtype)
            simple_ring_buffer.put_data(test_data, overwrite=True)

        # Verify last_written_index
        assert simple_ring_buffer.last_written_index.value == 9

        # Get latest data
        latest_data = simple_ring_buffer.get_latest_data()
        assert latest_data is not None
        assert latest_data.x == 9.0  # Last written value

        # Read sequentially
        # We should be able to read all 10 indices (0-9)
        for i in range(10):
            data = simple_ring_buffer.get_next_data()
            expected_index = i
            # The data at indices 0-4 has been overwritten with data from indices 5-9
            if i < 5:
                expected_value = float(i + 5)  # Values 5, 6, 7, 8, 9
            else:
                expected_value = float(i)  # Values 5, 6, 7, 8, 9
            assert data.x == expected_value
            assert simple_ring_buffer.last_read_index.value == expected_index

        # Now no more data available
        with pytest.raises(ValueError, match="No new data available to read"):
            simple_ring_buffer.get_next_data()
    def test_read_only_restrictions(self, example_data, simple_dtype):
        """Test read-only restrictions."""
        # Create read-only ring buffer
        read_only_buffer = SharedMemoryRingBuffer.create(
            example_data=example_data,
            read_only=True,
            ring_buffer_length=5
        )

        # Attempt to write data
        test_data = np.rec.array([(1.0, 2.0, 3.0)], dtype=simple_dtype)
        with pytest.raises(ValueError, match="Cannot write to read-only SharedMemoryRingBuffer"):
            read_only_buffer.put_data(test_data)

        # Attempt to get next data
        with pytest.raises(ValueError, match="Cannot call `get_next_data` on read-only SharedMemoryRingBuffer"):
            read_only_buffer.get_next_data()

        # Clean up
        read_only_buffer.close()

    def test_valid_flag(self, simple_ring_buffer):
        """Test valid flag functionality."""
        assert simple_ring_buffer.valid is True

        # Set valid to False
        simple_ring_buffer.valid = False
        assert simple_ring_buffer.valid is False

        # Set valid to True again
        simple_ring_buffer.valid = True
        assert simple_ring_buffer.valid is True

    def test_unlink_non_original(self, example_data):
        """Test unlinking a non-original SharedMemoryRingBuffer."""
        original = SharedMemoryRingBuffer.create(
            example_data=example_data,
            read_only=False,
            ring_buffer_length=5
        )
        dto = original.to_dto()
        copy = SharedMemoryRingBuffer.recreate(dto, read_only=False)

        with pytest.raises(ValueError, match="Cannot unlink a non-original SharedMemoryRingBuffer"):
            copy.unlink()

        # Clean up
        copy.close()
        original.close_and_unlink()

    def test_dtype_mismatch(self, simple_ring_buffer, simple_dtype):
        """Test putting data with mismatched dtype."""
        wrong_dtype = np.dtype([('a', np.int32), ('b', np.int32)])
        wrong_data = np.rec.array([(1, 2)], dtype=wrong_dtype)

        with pytest.raises(ValueError, match="Data type .* does not match SharedMemoryRingBuffer data type"):
            simple_ring_buffer.put_data(wrong_data)

    def test_memory_leak_large_data(self, large_ring_buffer, large_dtype):
        """Test for memory leaks when handling large data."""
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large data
        large_data = np.recarray((1,), dtype=large_dtype)

        # Number of iterations
        iterations = 5  # Reduced for faster tests

        # Put and get data in a loop
        for i in range(iterations):
            large_ring_buffer.put_data(large_data)
            retrieved = large_ring_buffer.get_latest_data()
            assert retrieved is not None

            # Force garbage collection
            gc.collect()

        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        # Log memory usage for debugging
        print(f"Memory before: {initial_memory:.2f} MB, after: {final_memory:.2f} MB, growth: {memory_growth:.2f} MB")

        # Allow for some memory growth, but not excessive
        assert memory_growth < 200, f"Excessive memory growth: {memory_growth} MB"

    def test_concurrent_access(self, example_data, simple_dtype):
        """Test concurrent access to shared memory from multiple processes."""
        # Create original ring buffer
        original = SharedMemoryRingBuffer.create(
            example_data=example_data,
            read_only=False,
            ring_buffer_length=10  # Larger buffer for concurrent testing
        )

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
        original.close_and_unlink()

    def test_sequential_reader(self, example_data, simple_dtype):
        """Test sequential reading with concurrent writing."""
        # Create original ring buffer
        original = SharedMemoryRingBuffer.create(
            example_data=example_data,
            read_only=False,
            ring_buffer_length=10  # Larger buffer for concurrent testing
        )

        # Create DTO and convert to dict for passing to child processes
        dto = original.to_dto()
        dto_dict = dto.model_dump()

        # Number of iterations
        iterations = 20  # Reduced for faster tests

        # Start sequential reader and writer processes
        reader = Process(target=sequential_reader_process_func, args=(dto_dict, iterations))
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
        original.close_and_unlink()

    def test_new_data_available(self, simple_ring_buffer, simple_dtype):
        """Test new_data_available property."""
        # Initially, no data is available
        assert simple_ring_buffer.new_data_available is False

        # Put data
        test_data = np.rec.array([(1.0, 2.0, 3.0)], dtype=simple_dtype)
        simple_ring_buffer.put_data(test_data)

        # Now data should be available
        assert simple_ring_buffer.new_data_available is True

        # Read the data
        simple_ring_buffer.get_next_data()

        # No new data available
        assert simple_ring_buffer.new_data_available is False

        # Put more data
        simple_ring_buffer.put_data(test_data)

        # New data available again
        assert simple_ring_buffer.new_data_available is True