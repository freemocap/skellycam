"""Tests for SharedMemoryRingBuffer and its supporting classes.

Covers the core shared memory IPC mechanism: creation, DTO round-trips,
read/write semantics, overwrite protection, and multi-reader scenarios.
"""
import numpy as np
import pytest

from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer


TEST_DTYPE = np.dtype([("x", np.float64), ("y", np.float64), ("z", np.float64)])
RING_LENGTH = 5


def _make_record(x: float, y: float, z: float) -> np.recarray:
    return np.rec.array([(x, y, z)], dtype=TEST_DTYPE)


# ---------------------------------------------------------------------------
# SharedMemoryElement
# ---------------------------------------------------------------------------

class TestSharedMemoryElement:
    def test_create_and_retrieve_data(self) -> None:
        element = SharedMemoryElement.create(dtype=TEST_DTYPE, read_only=False)
        try:
            data = _make_record(1.0, 2.0, 3.0)
            element.put_data(data)
            retrieved = element.retrieve_data()
            assert retrieved is not None
            assert float(retrieved.x) == pytest.approx(1.0)
            assert float(retrieved.y) == pytest.approx(2.0)
            assert float(retrieved.z) == pytest.approx(3.0)
        finally:
            element.unlink_and_close()

    def test_retrieve_before_write_returns_none(self) -> None:
        element = SharedMemoryElement.create(dtype=TEST_DTYPE, read_only=False)
        try:
            result = element.retrieve_data()
            assert result is None
        finally:
            element.unlink_and_close()

    def test_dto_roundtrip(self) -> None:
        original = SharedMemoryElement.create(dtype=TEST_DTYPE, read_only=False)
        try:
            original.put_data(_make_record(5.0, 6.0, 7.0))
            dto = original.to_dto()
            copy = SharedMemoryElement.recreate(dto=dto, read_only=True)
            try:
                retrieved = copy.retrieve_data()
                assert retrieved is not None
                assert float(retrieved.x) == pytest.approx(5.0)
            finally:
                copy.close()
        finally:
            original.unlink_and_close()

    def test_valid_flag_propagates(self) -> None:
        original = SharedMemoryElement.create(dtype=TEST_DTYPE, read_only=False)
        try:
            dto = original.to_dto()
            copy = SharedMemoryElement.recreate(dto=dto, read_only=True)
            try:
                assert copy.valid is True
                original.valid = False
                assert copy.valid is False
            finally:
                copy.close()
        finally:
            original.unlink_and_close()

    def test_dtype_mismatch_raises(self) -> None:
        element = SharedMemoryElement.create(dtype=TEST_DTYPE, read_only=False)
        try:
            wrong_dtype = np.dtype([("a", np.int32)])
            bad_data = np.rec.array([(42,)], dtype=wrong_dtype)
            with pytest.raises(ValueError, match="dtype"):
                element.put_data(bad_data)
        finally:
            element.unlink_and_close()

    def test_unlink_non_original_raises(self) -> None:
        original = SharedMemoryElement.create(dtype=TEST_DTYPE, read_only=False)
        try:
            dto = original.to_dto()
            copy = SharedMemoryElement.recreate(dto=dto, read_only=True)
            try:
                with pytest.raises(ValueError, match="non-original"):
                    copy.unlink()
            finally:
                copy.close()
        finally:
            original.unlink_and_close()


# ---------------------------------------------------------------------------
# SharedMemoryNumber
# ---------------------------------------------------------------------------

class TestSharedMemoryNumber:
    def test_create_and_read_value(self) -> None:
        num = SharedMemoryNumber.create(initial_value=42, read_only=False)
        try:
            assert num.value == 42
        finally:
            num.unlink_and_close()

    def test_write_and_read_value(self) -> None:
        num = SharedMemoryNumber.create(initial_value=0, read_only=False)
        try:
            num.value = 99
            assert num.value == 99
        finally:
            num.unlink_and_close()

    def test_cross_process_visibility_via_dto(self) -> None:
        original = SharedMemoryNumber.create(initial_value=10, read_only=False)
        try:
            dto = original.to_dto()
            reader = SharedMemoryNumber.recreate(dto=dto, read_only=True)
            try:
                assert reader.value == 10
                original.value = 777
                assert reader.value == 777
            finally:
                reader.close()
        finally:
            original.unlink_and_close()


# ---------------------------------------------------------------------------
# SharedMemoryRingBuffer
# ---------------------------------------------------------------------------

class TestSharedMemoryRingBuffer:
    @pytest.fixture()
    def ring(self) -> SharedMemoryRingBuffer:
        example = np.recarray((1,), dtype=TEST_DTYPE)
        buf = SharedMemoryRingBuffer.create(
            example_data=example,
            read_only=False,
            ring_buffer_length=RING_LENGTH,
        )
        yield buf
        buf.close_and_unlink()

    def test_initial_state(self, ring: SharedMemoryRingBuffer) -> None:
        assert ring.ring_buffer_length == RING_LENGTH
        assert ring.first_data_written is False
        assert ring.new_data_available is False

    def test_put_and_get_latest(self, ring: SharedMemoryRingBuffer) -> None:
        ring.put_data(_make_record(1.0, 2.0, 3.0))
        assert ring.first_data_written is True

        latest = ring.get_latest_data()
        assert float(latest.x[0]) == pytest.approx(1.0)

    def test_sequential_read(self, ring: SharedMemoryRingBuffer) -> None:
        ring.put_data(_make_record(10.0, 20.0, 30.0))
        ring.put_data(_make_record(40.0, 50.0, 60.0))

        assert ring.new_data_available is True
        first = ring.get_next_data(rec_array=None)
        assert float(first.x[0]) == pytest.approx(10.0)

        second = ring.get_next_data(rec_array=None)
        assert float(second.x[0]) == pytest.approx(40.0)

        assert ring.new_data_available is False

    def test_overwrite_protection(self, ring: SharedMemoryRingBuffer) -> None:
        """Writing past ring_length without reading should raise without overwrite_allowed."""
        # Ring has 5 slots. With read_index at -1, writing index 4 wraps to slot 4,
        # which collides with read_index -1 (since -1 % 5 == 4). So the 5th write triggers it.
        for i in range(RING_LENGTH - 1):
            ring.put_data(_make_record(float(i), 0.0, 0.0))

        with pytest.raises(ValueError, match="overwrite"):
            ring.put_data(_make_record(999.0, 0.0, 0.0), overwrite_allowed=False)

    def test_overwrite_allowed(self, ring: SharedMemoryRingBuffer) -> None:
        """Writing with overwrite_allowed=True should succeed past ring length."""
        for i in range(RING_LENGTH + 3):
            ring.put_data(_make_record(float(i), 0.0, 0.0), overwrite_allowed=True)

        latest = ring.get_latest_data()
        assert float(latest.x[0]) == pytest.approx(float(RING_LENGTH + 2))

    def test_get_data_by_index(self, ring: SharedMemoryRingBuffer) -> None:
        for i in range(3):
            ring.put_data(_make_record(float(i * 10), 0.0, 0.0))

        result = ring.get_data_by_index(index=1)
        assert float(result.x[0]) == pytest.approx(10.0)

    def test_get_data_by_index_out_of_bounds_raises(self, ring: SharedMemoryRingBuffer) -> None:
        ring.put_data(_make_record(1.0, 2.0, 3.0))
        with pytest.raises(IndexError):
            ring.get_data_by_index(index=5)

    def test_get_next_data_before_write_raises(self, ring: SharedMemoryRingBuffer) -> None:
        with pytest.raises(ValueError, match="not ready"):
            ring.get_next_data(rec_array=None)

    def test_dtype_mismatch_on_put_raises(self, ring: SharedMemoryRingBuffer) -> None:
        wrong_dtype = np.dtype([("a", np.int32)])
        bad_data = np.rec.array([(42,)], dtype=wrong_dtype)
        with pytest.raises(ValueError, match="data type"):
            ring.put_data(bad_data)

    def test_dto_roundtrip_and_cross_reader(self, ring: SharedMemoryRingBuffer) -> None:
        ring.put_data(_make_record(3.14, 2.71, 1.41))

        dto = ring.to_dto()
        reader = SharedMemoryRingBuffer.recreate(dto=dto, read_only=True)
        try:
            latest = reader.get_latest_data()
            assert float(latest.x[0]) == pytest.approx(3.14)
        finally:
            reader.close()

    def test_read_only_put_raises(self) -> None:
        example = np.recarray((1,), dtype=TEST_DTYPE)
        buf = SharedMemoryRingBuffer.create(
            example_data=example,
            read_only=True,
            ring_buffer_length=3,
        )
        try:
            with pytest.raises(ValueError, match="read-only"):
                buf.put_data(_make_record(1.0, 2.0, 3.0))
        finally:
            buf.close_and_unlink()

    def test_invalidated_buffer_raises_on_read(self, ring: SharedMemoryRingBuffer) -> None:
        ring.put_data(_make_record(1.0, 2.0, 3.0))
        ring.valid = False
        with pytest.raises(ValueError, match="invalid"):
            ring.get_data_by_index(index=0)
