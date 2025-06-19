import time
from multiprocessing import Process

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping


# Define process functions at module level so they can be pickled
def reader_process_func(dto, iterations):
    """Reader process function for multiprocessing tests."""
    # Convert dict back to DTO


    # Recreate ring buffer
    ring_buffer = FramePayloadSharedMemoryRingBuffer.recreate(dto, read_only=True)

    # Read in a loop
    for _ in range(iterations):
        try:
            if ring_buffer.new_frame_available:
                # Get the latest frame
                frame = ring_buffer.retrieve_latest_frame()
                assert isinstance(frame, FramePayload)
        except ValueError:
            # No data available yet
            pass
        time.sleep(0.01)

    # Clean up
    ring_buffer.close()


def sequential_reader_process_func(dto, iterations):
    """Sequential reader process function for multiprocessing tests."""
    # Convert dict back to DTO

    # Recreate ring buffer
    ring_buffer = FramePayloadSharedMemoryRingBuffer.recreate(dto, read_only=False)

    # Read in a loop
    read_count = 0
    for _ in range(iterations * 2):  # More iterations to ensure we catch all writes
        try:
            if ring_buffer.new_frame_available:
                frame = ring_buffer.retrieve_next_frame()
                assert isinstance(frame, FramePayload)
                read_count += 1
        except ValueError:
            # No data available yet
            pass
        time.sleep(0.01)

    # Clean up
    ring_buffer.close()
    return read_count


def writer_process_func(dto, iterations, camera_config_dict):
    """Writer process function for multiprocessing tests."""
    # Convert dict back to DTO
    camera_config = CameraConfig(**camera_config_dict)

    # Recreate ring buffer
    ring_buffer = FramePayloadSharedMemoryRingBuffer.recreate(dto, read_only=False)

    # Write in a loop
    for i in range(iterations):
        frame_rec_array = FramePayload.create_dummy(camera_config).to_numpy_record_array()
        ring_buffer.put_frame(frame_rec_array, overwrite=True)
        time.sleep(0.02)

    # Clean up
    ring_buffer.close()


class TestFramePayloadSharedMemoryRingBuffer:
    """Tests for the FramePayloadSharedMemoryRingBuffer class."""

    @pytest.fixture
    def camera_config(self):
        """Return a camera config for testing."""
        return CameraConfig()

    @pytest.fixture
    def timebase_mapping(self):
        """Return a timebase mapping for testing."""
        return TimebaseMapping()

    @pytest.fixture
    def example_frame_rec_array(self, camera_config, timebase_mapping):
        """Create example frame record array for testing."""
        return FramePayload.create_dummy(camera_config).to_numpy_record_array()

    @pytest.fixture
    def frame_buffer(self, camera_config):
        """Create and return a FramePayloadSharedMemoryRingBuffer."""
        buffer = FramePayloadSharedMemoryRingBuffer.from_config(
            camera_config=camera_config,
            read_only=False
        )
        yield buffer
        # Cleanup
        if buffer.valid:
            try:
                buffer.close_and_unlink()
            except Exception:
                pass

    def test_from_config(self, camera_config):
        """Test creating a FramePayloadSharedMemoryRingBuffer from a camera config."""
        buffer = FramePayloadSharedMemoryRingBuffer.from_config(
            camera_config=camera_config,
            read_only=False
        )
        
        assert buffer.valid
        assert buffer.first_data_written is False
        assert buffer.last_written_index.value == -1
        assert buffer.last_read_index.value == -1
        
        buffer.close_and_unlink()

    def test_put_and_retrieve_latest_frame(self, frame_buffer, example_frame_rec_array):
        """Test putting and retrieving the latest frame."""
        # Initially, no frame is available
        assert frame_buffer.new_frame_available is False
        with pytest.raises(ValueError, match="No data available to read"):
            frame_buffer.retrieve_latest_frame()

        # Put a frame into shared memory
        frame_buffer.put_frame(example_frame_rec_array, overwrite=False)

        # Verify frame is available
        assert frame_buffer.new_frame_available is True
        assert frame_buffer.first_data_written is True
        assert frame_buffer.last_written_index.value == 0

        # Retrieve the latest frame
        frame = frame_buffer.retrieve_latest_frame()

        # Verify frame data
        assert isinstance(frame, FramePayload)
        assert frame.frame_number == example_frame_rec_array.frame_metadata.frame_number
        assert frame.frame_metadata.camera_config.camera_id == example_frame_rec_array.frame_metadata.camera_config.camera_id
        
        # Put another frame
        example_frame_rec_array.frame_metadata.frame_number = 1
        frame_buffer.put_frame(example_frame_rec_array, overwrite=False)
        
        # Verify updated index
        assert frame_buffer.last_written_index.value == 1
        
        # Retrieve latest frame again
        frame = frame_buffer.retrieve_latest_frame()
        
        # Verify we get the newest frame
        assert frame.frame_number == 1

    def test_retrieve_next_frame(self, frame_buffer, example_frame_rec_array):
        """Test retrieving frames sequentially."""
        # Initially, no frame is available
        assert frame_buffer.new_frame_available is False
        with pytest.raises(ValueError, match="Ring buffer is not ready to read yet"):
            frame_buffer.retrieve_next_frame()

        # Put multiple frames
        for i in range(3):
            example_frame_rec_array.frame_metadata.frame_number = i
            frame_buffer.put_frame(example_frame_rec_array, overwrite=False)

        # Verify frames are available
        assert frame_buffer.new_frame_available is True
        assert frame_buffer.first_data_written is True
        assert frame_buffer.last_written_index.value == 2
        assert frame_buffer.last_read_index.value == -1

        # Retrieve frames sequentially
        for i in range(3):
            frame = frame_buffer.retrieve_next_frame()
            assert frame.frame_number == i
            assert frame_buffer.last_read_index.value == i

        # No more frames available
        assert frame_buffer.new_frame_available is False
        with pytest.raises(ValueError, match="No new data available to read"):
            frame_buffer.retrieve_next_frame()

    def test_read_only_restrictions(self, camera_config, example_frame_rec_array):
        """Test read-only restrictions."""
        # Create read-only buffer
        read_only_buffer = FramePayloadSharedMemoryRingBuffer.from_config(
            camera_config=camera_config,
            read_only=True
        )

        # Attempt to put a frame
        with pytest.raises(ValueError, match="Cannot put new frame into read-only instance of shared memory!"):
            read_only_buffer.put_frame(example_frame_rec_array, overwrite=False)

        # Clean up
        read_only_buffer.close()

    def test_concurrent_access(self, camera_config):
        """Test concurrent access to shared memory from multiple processes."""
        # Create original buffer
        original = FramePayloadSharedMemoryRingBuffer.from_config(
            camera_config=camera_config,
            read_only=False
        )

        # Create DTO and convert to dict for passing to child processes
        dto = original.to_dto()
        dto_dict = dto.model_dump()
        camera_config_dict = camera_config.model_dump()

        # Number of iterations
        iterations = 10

        # Start reader and writer processes
        reader = Process(target=reader_process_func, args=(dto_dict, iterations))
        writer = Process(target=writer_process_func, args=(dto_dict, iterations, camera_config_dict))

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

    def test_sequential_reader(self, camera_config):
        """Test sequential reading with concurrent writing."""
        # Create original buffer
        original = FramePayloadSharedMemoryRingBuffer.from_config(
            camera_config=camera_config,
            read_only=False
        )

        # Create DTO and convert to dict for passing to child processes
        dto = original.to_dto()

        camera_config_dict = camera_config.model_dump()

        # Number of iterations
        iterations = 10

        # Start sequential reader and writer processes
        reader = Process(target=sequential_reader_process_func, args=(dto, iterations))
        writer = Process(target=writer_process_func, args=(dto, iterations, camera_config_dict))

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

    def test_buffer_wrapping(self, frame_buffer, example_frame_rec_array):
        """Test buffer wrapping behavior."""
        # Fill the buffer and then some to test wrapping
        buffer_size = frame_buffer.ring_buffer_length
        total_frames = buffer_size + 5

        for i in range(total_frames):
            example_frame_rec_array.frame_metadata.frame_number = i
            frame_buffer.put_frame(example_frame_rec_array, overwrite=True)

        # Verify last_written_index
        assert frame_buffer.last_written_index.value == total_frames - 1

        # Get latest frame
        latest_frame = frame_buffer.retrieve_latest_frame()
        assert latest_frame is not None
        assert latest_frame.frame_number == total_frames - 1

        # Reset the last_read_index to start reading from the oldest available frame
        # This is needed because the buffer has wrapped around
        frame_buffer.last_read_index.value = total_frames - buffer_size - 1

        # Read sequentially - we should get the most recent buffer_size frames
        for i in range(buffer_size):
            frame = frame_buffer.retrieve_next_frame()
            expected_frame_number = total_frames - buffer_size + i
            assert frame.frame_number == expected_frame_number

        # Now no more frames available
        with pytest.raises(ValueError, match="No new data available to read"):
            frame_buffer.retrieve_next_frame()

    def test_timestamps_are_updated(self, frame_buffer, example_frame_rec_array):
        """Test that timestamps are updated when putting and retrieving frames."""
        # Put a frame
        before_put = time.perf_counter_ns()
        frame_buffer.put_frame(example_frame_rec_array, overwrite=False)
        after_put = time.perf_counter_ns()
        
        # Verify timestamp was set
        copy_to_shm_ns = example_frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns
        assert before_put <= copy_to_shm_ns <= after_put
        
        # Retrieve the frame
        before_retrieve = time.perf_counter_ns()
        frame = frame_buffer.retrieve_latest_frame()
        after_retrieve = time.perf_counter_ns()
        
        # Verify timestamp was set
        retrieve_from_shm_ns = frame.frame_metadata.timestamps.post_retrieve_from_camera_shm_ns
        assert before_retrieve <= retrieve_from_shm_ns <= after_retrieve