import multiprocessing
import time
from typing import List

import numpy as np

from skellycam.core.memory.shared_memory_indexed_array import SharedMemoryIndexedArrayDTO, SharedMemoryIndexedArray



def producer(shared_dto: SharedMemoryIndexedArrayDTO, data: List[np.ndarray]):
    shm_array = SharedMemoryIndexedArray.recreate_from_dto(shared_dto)
    data_length = len(data)
    for _ in range(10):
        for array in data:
            print(f"Producer - Putting array into shared memory index: {shm_array.last_written_index.value + 1} (wrapped index: {(shm_array.last_written_index.value+1)%data_length})")

            shm_array.put_payload(array)
            time.sleep(0.001)


def fast_consumer(shared_dto: SharedMemoryIndexedArrayDTO,
                  data: List[np.ndarray],
                  shutdown_flag: multiprocessing.Value):
    shm_array = SharedMemoryIndexedArray.recreate_from_dto(shared_dto)
    index = 0
    data_length = len(data)
    while not shutdown_flag.value:
        if shm_array.new_data_available:
            received_array = shm_array.get_next_payload()
            print(
                f"Fast Consumer - Received array from shared memory index: {shm_array.last_read_index.value} (wrapped index: {shm_array.last_read_index.value % data_length})")

            assert np.array_equal(received_array, data[index%data_length]), f"Data mismatch at index {index}"
            index += 1
        time.sleep(0.0001)


def slow_consumer(shared_dto: SharedMemoryIndexedArrayDTO,
                  data: List[np.ndarray],
                  shutdown_flag: multiprocessing.Value):
    shm_array = SharedMemoryIndexedArray.recreate_from_dto(shared_dto)
    index = 0
    data_length = len(data)
    time.sleep(.001)
    while not shutdown_flag.value:
        if shm_array.new_data_available:
            received_array = shm_array.get_next_payload()
            print(f"Slow Consumer - Received array from shared memory index: {shm_array.last_read_index.value} (wrapped index: {shm_array.last_read_index.value%data_length})")
            assert np.array_equal(received_array, data[index%data_length]), f"Data mismatch at index {index}"
            index += 1
        time.sleep(1)  # should cause the producer to overwrite the data, so the consumer will fail


def ppptest_shared_memory_indexed_array():
    array_size = 3
    shm_element_shape = (10, 10)
    dtype = np.float32
    random_data = [np.random.rand(*shm_element_shape).astype(dtype) for _ in range(array_size)]
    shutdown_flag = multiprocessing.Value('b', False)
    shared_array = SharedMemoryIndexedArray.create(shm_element_shape, dtype, array_size)
    shared_dto = shared_array.to_dto()

    producer_process = multiprocessing.Process(target=producer, args=(shared_dto, random_data))
    consumer_process = multiprocessing.Process(target=fast_consumer, args=(shared_dto, random_data, shutdown_flag))

    producer_process.start()
    consumer_process.start()

    producer_process.join()
    shutdown_flag.value = True
    consumer_process.join()

    shared_array.close_and_unlink()


def oootest_shared_memory_indexed_array_overwrite_protection():
    array_size = 3
    shm_element_shape = (10, 10)
    dtype = np.float32
    random_data = [np.random.rand(*shm_element_shape).astype(dtype) for _ in range(array_size)]
    shutdown_flag = multiprocessing.Value('b', False)
    shared_array = SharedMemoryIndexedArray.create(shm_element_shape, dtype, array_size)
    shared_dto = shared_array.to_dto()

    producer_process = multiprocessing.Process(target=producer, args=(shared_dto, random_data))
    consumer_process = multiprocessing.Process(target=slow_consumer, args=(shared_dto, random_data, shutdown_flag))

    producer_process.start()
    consumer_process.start()

    producer_process.join()
    shutdown_flag.value = True
    consumer_process.join()

    shared_array.close_and_unlink()


if __name__ == "__main__":
    ppptest_shared_memory_indexed_array()
    print("-------------------------------------------------\n-------------------------------------------------")
    oootest_shared_memory_indexed_array_overwrite_protection() #should fail
