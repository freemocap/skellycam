from multiprocessing import shared_memory
from typing import Tuple

import numpy as np
import pytest

from skellycam.core.memory.shared_memory_element import SharedMemoryElement


def test_create(numpy_array_definition_fixture: Tuple[Tuple[int], np.dtype]):
    shape, dtype = numpy_array_definition_fixture
    if dtype == str:
        with pytest.raises(ValueError):
            SharedMemoryElement.create(shape=shape, dtype=dtype)
        return

    element = SharedMemoryElement.create(shape=shape, dtype=dtype)

    assert element.buffer.shape == shape
    assert element.buffer.dtype == dtype
    assert isinstance(element.shm, shared_memory.SharedMemory)

    element.close()
    element.unlink()


def test_recreate(varied_numpy_data: Tuple[Tuple[int], np.dtype]):
    shape, dtype = varied_numpy_data
    element = SharedMemoryElement.create(shape=shape, dtype=dtype)
    shm_name = element.name

    recreated_element = SharedMemoryElement.recreate(shm_name, shape, dtype)

    assert recreated_element.buffer.shape == shape
    assert recreated_element.buffer.dtype == dtype
    assert recreated_element.name == shm_name

    element.close()
    element.unlink()
    recreated_element.close()


def test_copy_into_buffer(varied_numpy_data: Tuple[Tuple[int], np.dtype]):
    shape, dtype = varied_numpy_data
    element = SharedMemoryElement.create(shape=shape, dtype=dtype)

    buffer = np.zeros(shape, dtype=dtype)
    element.copy_into_buffer(buffer)

    assert np.array_equal(buffer, element.buffer)

    element.close()
    element.unlink()


def test_copy_from_buffer(varied_numpy_data: Tuple[Tuple[int], np.dtype]):
    shape, dtype = varied_numpy_data
    element = SharedMemoryElement.create(shape=shape, dtype=dtype)

    buffer_view = element.copy_from_buffer()

    assert isinstance(buffer_view, memoryview)
    assert buffer_view.shape == shape
    assert all([stride % element.buffer.itemsize == 0 for stride in buffer_view.strides])

    element.close()
    element.unlink()


def test_close(varied_numpy_data: Tuple[Tuple[int], np.dtype]):
    shape, dtype = varied_numpy_data
    element = SharedMemoryElement.create(shape=shape, dtype=dtype)

    element.close()

    with pytest.raises(OSError):
        element.shm.buf[:]

    element.unlink()


def test_unlink(varied_numpy_data: Tuple[Tuple[int], np.dtype]):
    shape, dtype = varied_numpy_data
    element = SharedMemoryElement.create(shape=shape, dtype=dtype)

    element.close()
    element.unlink()

    with pytest.raises(FileNotFoundError):
        shared_memory.SharedMemory(name=element.name)
