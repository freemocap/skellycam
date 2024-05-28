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


def test_recreate(ndarray_shape_fixture, dtype_fixture: np.dtype):
    element = SharedMemoryElement.create(shape=ndarray_shape_fixture,
                                         dtype=dtype_fixture)
    shm_name = element.name

    recreated_element = SharedMemoryElement.recreate(
        shm_name=shm_name,
        shape=ndarray_shape_fixture,
        dtype=dtype_fixture
    )

    assert recreated_element.buffer.shape == ndarray_shape_fixture
    assert recreated_element.buffer.dtype == dtype_fixture
    assert recreated_element.name == shm_name

    element.close()
    recreated_element.close()
    element.unlink()


def test_copy_into_buffer(ndarray_shape_fixture, dtype_fixture: np.dtype):
    element = SharedMemoryElement.create(shape=ndarray_shape_fixture, dtype=dtype_fixture)

    buffer = np.zeros(ndarray_shape_fixture, dtype=dtype_fixture)
    element.copy_into_buffer(buffer)

    assert np.array_equal(buffer, element.buffer)

    element.close()
    element.unlink()


def test_copy_from_buffer(random_array_fixture: np.ndarray):
    element = SharedMemoryElement.create(shape=random_array_fixture.shape,
                                         dtype=random_array_fixture.dtype)
    element.copy_into_buffer(random_array_fixture)
    copied_npy = element.copy_from_buffer()

    assert isinstance(copied_npy, np.ndarray)
    assert copied_npy.shape == random_array_fixture.shape
    assert copied_npy.dtype == random_array_fixture.dtype
    assert np.array_equal(copied_npy, element.buffer)
    assert np.array_equal(copied_npy, random_array_fixture)

    # ensure that the copied numpy array is a copy and not a view
    assert not np.shares_memory(copied_npy, element.buffer)
    copied_npy[:] = 0
    assert not np.array_equal(copied_npy, element.buffer)
    assert not np.array_equal(copied_npy, random_array_fixture)
    element.close()
    element.unlink()


def test_close(ndarray_shape_fixture, dtype_fixture: np.dtype):
    element = SharedMemoryElement.create(shape=ndarray_shape_fixture,
                                         dtype=dtype_fixture)
    assert isinstance(element.shm, shared_memory.SharedMemory)
    assert isinstance(element, SharedMemoryElement)
    element.close()

    with pytest.raises(TypeError):
        element.shm.buf[:]

    element.unlink()


def test_unlink(ndarray_shape_fixture, dtype_fixture: np.dtype):
    element = SharedMemoryElement.create(shape=ndarray_shape_fixture,
                                         dtype=dtype_fixture)

    element.close()
    element.unlink()

    with pytest.raises(FileNotFoundError):
        shared_memory.SharedMemory(name=element.name)