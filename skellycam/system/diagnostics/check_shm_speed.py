import multiprocessing
import time
from time import sleep
from typing import Tuple

import numpy as np
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_shared_memory import \
    SharedMemoryRingBufferDTO, SharedMemoryRingBuffer


def writer_process(ring_buffer_dto: SharedMemoryRingBufferDTO,
                   num_payloads: int,
                   payload_shape: Tuple[int, ...],
                   dtype: np.dtype):
    ring_buffer = SharedMemoryRingBuffer.recreate(ring_buffer_dto, read_only=False)
    time.sleep(1.0)
    durations = []
    for i in range(num_payloads):
        # Create test data
        data = np.full(payload_shape, i, dtype=dtype)
        time.sleep(0.1)
        tik = time.perf_counter_ns()
        ring_buffer.put_data(data)
        tok = time.perf_counter_ns()
        durations.append(tok - tik)
        print(f">>Writer: Written payload {i} with max value {data.max()} in {durations[-1] / 1e6:.3f} ms")
    sleep(.5)
    print(f"\n\nWriter: Average write duration: {np.mean(durations) / 1e6:.3f} ms")


def reader_process(ring_buffer_dto: SharedMemoryRingBufferDTO):
    ring_buffer = SharedMemoryRingBuffer.recreate(ring_buffer_dto, read_only=False)
    read_data = []
    attempts = 0
    durations = []
    while not ring_buffer.ready_to_read:
        sleep(0.001)
    print("Reader: SHM ready to read")
    while attempts < 1e3:
        if ring_buffer.new_data_available:
            attempts = 0
            tik = time.perf_counter_ns()
            data = ring_buffer.get_next_payload()
            tok = time.perf_counter_ns()
            durations.append(tok - tik)
            read_data.append(data)
            print(f"<<READER: Read payload {ring_buffer.last_read_index.get()} with max value {data.max()} in {durations[-1] / 1e6:.3f} ms")
        else:
            attempts += 1
            sleep(0.002)
    sleep(0.5)
    print(f">>Reader: Average read duration: {np.mean(durations) / 1e6:.3f} ms")
    return read_data


def watcher_process(ring_buffer_dto: SharedMemoryRingBufferDTO):
    ring_buffer = SharedMemoryRingBuffer.recreate(ring_buffer_dto, read_only=True)
    watched_data = []
    last_data_max = -1
    durations = []
    attempts = 0
    while not ring_buffer.ready_to_read:
        sleep(0.001)
    print(">>>>Watcher: SHM ready to read")
    while attempts < 1e3:
        if ring_buffer.new_data_available:
            attempts = 0
            tik = time.perf_counter_ns()
            data = ring_buffer.get_latest_payload()
            tok = time.perf_counter_ns()
            durations.append(tok - tik)
            watched_data.append(data)
            print(f"\tWATCHER: Read payload {ring_buffer.last_read_index.get()} with max value {data.max()} in {durations[-1] / 1e6:.3f} ms")
        else:
            attempts += 1
            sleep(0.0015)
    sleep(0.5)
    print(f"\n\nWatcher: Average read duration: {np.mean(durations) / 1e6:.3f} ms\n\n")
    return watched_data


def check_shared_memory_ring_buffer_multiprocess():
    print(f"Testing SharedMemoryRingBuffer with multiple processes...")
    # Define parameters
    num_payloads = 10
    payload_shape = (1080, 1920, 3)

    # Test with np.ndarray payload
    dtype = np.uint8
    example_payload = np.ones(payload_shape, dtype=dtype)


    # Create a ring buffer
    ring_buffer = SharedMemoryRingBuffer.create(
        example_payload=example_payload,
        dtype=dtype,
        read_only=True,
    )
    print(f"Ring buffer created with shape {ring_buffer.ring_buffer_shape} and dtype {ring_buffer.dtype}")

    # Start writer and reader processes
    writer = multiprocessing.Process(target=writer_process, args=(ring_buffer.to_dto(),
                                                                  num_payloads,
                                                                  payload_shape,
                                                                  dtype))
    reader = multiprocessing.Process(target=reader_process, args=(ring_buffer.to_dto(),
                                                                  ))
    watcher = multiprocessing.Process(target=watcher_process, args=(ring_buffer.to_dto(),
                                                                  ))

    try:
        writer.start()
        reader.start()
        watcher.start()

        writer.join()
        reader.join()
        watcher.join()

        print(f"Multi-process test completed .")
    except Exception as e:
        print(f"Test failed : {e}")
        raise
    finally:
        # Clean up shared memory
        ring_buffer.close_and_unlink()



if __name__ == "__main__":
    check_shared_memory_ring_buffer_multiprocess()