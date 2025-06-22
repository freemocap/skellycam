import time
from multiprocessing import Process

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.multi_frame_payload_ring_buffer import MultiFrameSharedMemoryRingBuffer
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping


# Define process functions at module level so they can be pickled
def reader_process_func(dto_dict, iterations):
    """Reader process function for multiprocessing tests."""
    # Convert dict back to DTO
    from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
    dto = SharedMemoryRingBufferDTO(**dto_dict)

    # Recreate ring buffer
    ring_buffer = MultiFrameSharedMemoryRingBuffer.recreate(dto, read_only=True)

    # Create a pre-allocated recarray for reading
    frame_dtype = dto.dtype
    output_frame = np.recarray((1,), dtype=frame_dtype)

    # Read in a loop
    for _ in range(iterations):
        try:
            if ring_buffer.first_data_written:
                # Get the latest frame
                frame = ring_buffer.get_latest_multiframe(output_frame)
                assert isinstance(frame, np.recarray)
        except ValueError:
            # No data available yet
            pass
        time.sleep(0.01)

    # Clean up
    ring_buffer.close()


def sequential_reader_process_func(dto_dict, iterations):
    """Sequential reader process function for multiprocessing tests."""
    # Convert dict back to DTO
    from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
    dto = SharedMemoryRingBufferDTO(**dto_dict)

    # Recreate ring buffer
    ring_buffer = MultiFrameSharedMemoryRingBuffer.recreate(dto, read_only=False)

    # Create a pre-allocated recarray for reading
    frame_dtype = dto.dtype
    output_frame = np.recarray((1,), dtype=frame_dtype)

    # Read in a loop
    read_count = 0
    for _ in range(iterations * 2):  # More iterations to ensure we catch all writes
        try:
            if ring_buffer.new_data_available:
                frame = ring_buffer.get_next_multiframe(output_frame)
                assert isinstance(frame, np.recarray)
                read_count += 1
        except ValueError:
            # No data available yet
            pass
        time.sleep(0.01)

    # Clean up
    ring_buffer.close()
    return read_count


def writer_process_func(dto_dict, iterations, camera_configs_dict, timebase_mapping_dict):
    """Writer process function for multiprocessing tests."""
    # Convert dict back to DTO
    from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
    dto = SharedMemoryRingBufferDTO(**dto_dict)

    # Recreate camera configs
    camera_configs = CameraConfigs()
    for camera_id, config_dict in camera_configs_dict.items():
        camera_configs[camera_id] = CameraConfig(**config_dict)

    # Recreate timebase mapping
    timebase_mapping = TimebaseMapping(**timebase_mapping_dict)

    # Recreate ring buffer
    ring_buffer = MultiFrameSharedMemoryRingBuffer.recreate(dto, read_only=False)

    # Write in a loop
    for i in range(iterations):
        # Create a dummy MultiFramePayload and convert to recarray
        mf_payload = MultiFramePayload.create_dummy(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping
        )
        # Update frame numbers to match iteration
        for camera_id, frame in mf_payload.frames.items():
            frame.frame_metadata.frame_number = i

        mf_rec_array = mf_payload.to_numpy_record_array()
        ring_buffer.put_multiframe(mf_rec_array, overwrite=True)
        time.sleep(0.02)

    # Clean up
    ring_buffer.close()


class TestMultiFrameSharedMemoryRingBuffer:
    """Tests for the MultiFrameSharedMemoryRingBuffer class."""

    @pytest.fixture
    def camera_configs(self):
        """Return camera configs for testing."""
        configs = CameraConfigs()
        configs["camera1"] = CameraConfig(camera_id="camera1",camera_index=1)
        configs["camera2"] = CameraConfig(camera_id="camera2",camera_index=2)
        return configs

    @pytest.fixture
    def timebase_mapping(self):
        """Return a timebase mapping for testing."""
        return TimebaseMapping()

    @pytest.fixture
    def example_multiframe_payload(self, camera_configs, timebase_mapping):
        """Create example MultiFramePayload for testing."""
        return MultiFramePayload.create_dummy(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping
        )

    @pytest.fixture
    def example_multiframe_rec_array(self, example_multiframe_payload):
        """Create example multiframe record array for testing."""
        return example_multiframe_payload.to_numpy_record_array()

    @pytest.fixture
    def multiframe_buffer(self, camera_configs, timebase_mapping):
        """Create and return a MultiFrameSharedMemoryRingBuffer."""
        buffer = MultiFrameSharedMemoryRingBuffer.from_configs(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping,
            read_only=False
        )
        yield buffer
        # Cleanup
        if buffer.valid:
            try:
                buffer.close_and_unlink()
            except Exception:
                pass

    @pytest.fixture
    def output_multiframe(self, example_multiframe_rec_array):
        """Create a pre-allocated recarray for reading multiframes."""
        return example_multiframe_rec_array.copy()

    def test_from_configs(self, camera_configs, timebase_mapping):
        """Test creating a MultiFrameSharedMemoryRingBuffer from camera configs."""
        buffer = MultiFrameSharedMemoryRingBuffer.from_configs(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping,
            read_only=False
        )

        assert buffer.valid
        assert buffer.first_data_written is False
        assert buffer.last_written_index.value == -1
        assert buffer.last_read_index.value == -1

        buffer.close_and_unlink()

    def test_put_and_get_latest_multiframe(self, multiframe_buffer, example_multiframe_rec_array, output_multiframe):
        """Test putting and retrieving the latest multiframe."""
        # Initially, no frame is available
        assert multiframe_buffer.first_data_written is False

        # Get latest should return the input array when no data is available
        result = multiframe_buffer.get_latest_multiframe(output_multiframe)
        assert np.array_equal(result, output_multiframe)

        # Put a multiframe into shared memory
        multiframe_buffer.put_multiframe(example_multiframe_rec_array, overwrite=False)

        # Verify frame is available
        assert multiframe_buffer.first_data_written is True
        assert multiframe_buffer.last_written_index.value == 0

        # Retrieve the latest multiframe
        result = multiframe_buffer.get_latest_multiframe(output_multiframe)

        # Verify multiframe data
        assert isinstance(result, np.recarray)

        # Check frame numbers for each camera
        for camera_id in example_multiframe_rec_array.dtype.names:
            assert result[camera_id].frame_metadata.frame_number[0] == \
                   example_multiframe_rec_array[camera_id].frame_metadata.frame_number[0]
            assert result[camera_id].frame_metadata.camera_config.camera_id[0] == \
                   example_multiframe_rec_array[camera_id].frame_metadata.camera_config.camera_id[0]

        # Put another multiframe with updated frame numbers
        for camera_id in example_multiframe_rec_array.dtype.names:
            example_multiframe_rec_array[camera_id].frame_metadata.frame_number[0] = 1
        multiframe_buffer.put_multiframe(example_multiframe_rec_array, overwrite=False)

        # Verify updated index
        assert multiframe_buffer.last_written_index.value == 1

        # Retrieve latest multiframe again
        result = multiframe_buffer.get_latest_multiframe(output_multiframe)

        # Verify we get the newest frame
        for camera_id in result.dtype.names:
            assert result[camera_id].frame_metadata.frame_number[0] == 1

    def test_get_next_multiframe(self, multiframe_buffer, example_multiframe_rec_array, output_multiframe):
        """Test retrieving multiframes sequentially."""
        # Put multiple multiframes
        for i in range(3):
            for camera_id in example_multiframe_rec_array.dtype.names:
                example_multiframe_rec_array[camera_id].frame_metadata.frame_number = i
            multiframe_buffer.put_multiframe(example_multiframe_rec_array, overwrite=False)

        # Verify multiframes are available
        assert multiframe_buffer.first_data_written is True
        assert multiframe_buffer.last_written_index.value == 2
        assert multiframe_buffer.last_read_index.value == -1

        # Retrieve multiframes sequentially
        for i in range(3):
            result = multiframe_buffer.get_next_multiframe()
            for camera_id in result.dtype.names:
                assert result[camera_id].frame_metadata.frame_number == i
            assert multiframe_buffer.last_read_index.value == i

        # No more multiframes available
        assert multiframe_buffer.new_data_available is False

    def test_read_only_restrictions(self, camera_configs, timebase_mapping, example_multiframe_rec_array):
        """Test read-only restrictions."""
        # Create read-only buffer
        read_only_buffer = MultiFrameSharedMemoryRingBuffer.from_configs(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping,
            read_only=True
        )

        # Attempt to put a multiframe
        with pytest.raises(ValueError, match="Cannot write to read-only shared memory!"):
            read_only_buffer.put_multiframe(example_multiframe_rec_array, overwrite=False)

        # Clean up
        read_only_buffer.close()

    def test_concurrent_access(self, camera_configs, timebase_mapping):
        """Test concurrent access to shared memory from multiple processes."""
        # Create original buffer
        original = MultiFrameSharedMemoryRingBuffer.from_configs(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping,
            read_only=False
        )

        # Create DTO and convert to dict for passing to child processes
        dto = original.to_dto()
        dto_dict = dto.model_dump()

        # Convert camera configs to dict
        camera_configs_dict = {camera_id: config.model_dump() for camera_id, config in camera_configs.items()}
        timebase_mapping_dict = timebase_mapping.model_dump()

        # Number of iterations
        iterations = 10

        # Start reader and writer processes
        reader = Process(target=reader_process_func, args=(dto_dict, iterations))
        writer = Process(target=writer_process_func,
                         args=(dto_dict, iterations, camera_configs_dict, timebase_mapping_dict))

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

    def test_sequential_reader(self, camera_configs, timebase_mapping):
        """Test sequential reading with concurrent writing."""
        # Create original buffer
        original = MultiFrameSharedMemoryRingBuffer.from_configs(
            camera_configs=camera_configs,
            timebase_mapping=timebase_mapping,
            read_only=False
        )

        # Create DTO and convert to dict for passing to child processes
        dto = original.to_dto()
        dto_dict = dto.model_dump()

        # Convert camera configs to dict
        camera_configs_dict = {camera_id: config.model_dump() for camera_id, config in camera_configs.items()}
        timebase_mapping_dict = timebase_mapping.model_dump()

        # Number of iterations
        iterations = 10

        # Start sequential reader and writer processes
        reader = Process(target=sequential_reader_process_func, args=(dto_dict, iterations))
        writer = Process(target=writer_process_func,
                         args=(dto_dict, iterations, camera_configs_dict, timebase_mapping_dict))

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

    def test_buffer_wrapping(self, multiframe_buffer, example_multiframe_rec_array, output_multiframe):
        """Test buffer wrapping behavior."""
        # Fill the buffer and then some to test wrapping
        buffer_size = multiframe_buffer.ring_buffer_length
        total_frames = buffer_size + 5

        for i in range(total_frames):
            for camera_id in example_multiframe_rec_array.dtype.names:
                example_multiframe_rec_array[camera_id].frame_metadata.frame_number[0] = i
            multiframe_buffer.put_multiframe(example_multiframe_rec_array, overwrite=True)

        # Verify last_written_index
        assert multiframe_buffer.last_written_index.value == total_frames - 1

        # Get latest multiframe
        latest_frame = multiframe_buffer.get_latest_multiframe(output_multiframe)
        assert latest_frame is not None
        for camera_id in latest_frame.dtype.names:
            assert latest_frame[camera_id].frame_metadata.frame_number[0] == total_frames - 1

        # Reset the last_read_index to start reading from the oldest available frame
        # This is needed because the buffer has wrapped around
        multiframe_buffer.last_read_index.value = total_frames - buffer_size - 1

        # Read sequentially - we should get the most recent buffer_size frames
        for i in range(buffer_size):
            frame = multiframe_buffer.get_next_multiframe()
            expected_frame_number = total_frames - buffer_size + i
            for camera_id in frame.dtype.names:
                assert frame[camera_id].frame_metadata.frame_number == expected_frame_number

    def test_timestamps_are_updated(self, multiframe_buffer, example_multiframe_rec_array, output_multiframe):
        """Test that timestamps are updated when putting and retrieving multiframes."""
        # Put a multiframe
        before_put = time.perf_counter_ns()
        multiframe_buffer.put_multiframe(example_multiframe_rec_array, overwrite=False)
        after_put = time.perf_counter_ns()

        # Verify timestamps were set for each camera
        for camera_id in example_multiframe_rec_array.dtype.names:
            pre_copy_ts = \
            example_multiframe_rec_array[camera_id].frame_metadata.timestamps.pre_copy_to_multiframe_shm_ns[0]
            assert before_put <= pre_copy_ts <= after_put

        # Retrieve the multiframe
        before_retrieve = time.perf_counter_ns()
        frame = multiframe_buffer.get_latest_multiframe(output_multiframe)
        after_retrieve = time.perf_counter_ns()

        # Verify timestamps were set for each camera
        for camera_id in frame.dtype.names:
            post_retrieve_ts = frame[camera_id].frame_metadata.timestamps.post_retrieve_from_multiframe_shm_ns[0]
            pre_retrieve_ts = frame[camera_id].frame_metadata.timestamps.pre_retrieve_from_multiframe_shm_ns[0]
            assert before_retrieve <= post_retrieve_ts <= after_retrieve
            assert before_retrieve <= pre_retrieve_ts <= after_retrieve

    def test_get_all_new_multiframes(self, multiframe_buffer, example_multiframe_rec_array, output_multiframe):
        """Test retrieving all new multiframes."""
        # Put multiple multiframes
        for i in range(3):
            for camera_id in example_multiframe_rec_array.dtype.names:
                example_multiframe_rec_array[camera_id].frame_metadata.frame_number[0] = i
            multiframe_buffer.put_multiframe(example_multiframe_rec_array, overwrite=False)

        # Get all new multiframes
        multiframes = multiframe_buffer.get_all_new_multiframes()

        # Verify we got all 3 multiframes
        assert len(multiframes) == 3

        # Verify frame numbers
        for i, mf in enumerate(multiframes):
            for camera_id in mf.dtype.names:
                assert mf[camera_id].frame_metadata.frame_number == i

        # Verify no more new multiframes
        assert len(multiframe_buffer.get_all_new_multiframes()) == 0

    def test_conversion_between_multiframe_payload_and_recarray(self, example_multiframe_payload,
                                                                example_multiframe_rec_array):
        """Test conversion between MultiFramePayload and numpy recarray."""
        # Test conversion from MultiFramePayload to recarray
        rec_array = example_multiframe_payload.to_numpy_record_array()
        assert isinstance(rec_array, np.recarray)

        # Test conversion from recarray to MultiFramePayload
        mf_payload = MultiFramePayload.from_numpy_record_array(rec_array)
        assert isinstance(mf_payload, MultiFramePayload)

        # Verify data integrity
        for camera_id in example_multiframe_payload.camera_ids:
            original_frame = example_multiframe_payload.frames[camera_id]
            converted_frame = mf_payload.frames[camera_id]

            assert original_frame.frame_metadata.frame_number == converted_frame.frame_metadata.frame_number
            assert original_frame.frame_metadata.camera_config.camera_id == converted_frame.frame_metadata.camera_config.camera_id