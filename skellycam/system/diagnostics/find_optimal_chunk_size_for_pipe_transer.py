import multiprocessing
import time
from typing import Tuple

def worker(connection: multiprocessing.Pipe, data_size: int) -> None:
    data = bytearray(data_size)
    connection.send_bytes(data)
    connection.close()

def measure_time(chunk_size: int, data_size: int) -> float:
    parent_conn, child_conn = multiprocessing.Pipe()#duplex=True)
    start_time = time.perf_counter_ns()
    process = multiprocessing.Process(target=worker, args=(child_conn, data_size))
    process.start()
    try:
        while True:
            size_to_receive = min(chunk_size, data_size)
            if size_to_receive == 0:
                break
            received_bytes = parent_conn.recv_bytes()
            data_size -= len(received_bytes)
    except (BrokenPipeError, ValueError) as e:
        print(f"Failed at chunk size {chunk_size}: {e}")
        return float('inf')
    process.join()
    end_time = time.perf_counter_ns()
    return (end_time - start_time) / 1e9

def find_optimal_chunk_size(data_size: int) -> Tuple[int, float]:
    best_time = float('inf')
    best_chunk_size = None
    chunk_size = 2**10  # Start with 1 KB

    while chunk_size <= data_size:
        # print(f"Measuring time for to send {data_size/1024/1024} MB with chunk size {chunk_size/1024/1024} MB...")
        elapsed_time = measure_time(chunk_size, data_size)

        if elapsed_time == float('inf'):  # Stop if pipe fails
            break
        print(f"Chunk Size: {chunk_size/1024/1024:.3} MB, Time: {elapsed_time:.3f} seconds")
        if elapsed_time < best_time:
            best_time = elapsed_time
            best_chunk_size = chunk_size
        chunk_size *= 2  # Double the chunk size each iteration

    return best_chunk_size, best_time

if __name__ == "__main__":
    # 1 GB
    data_size = 2 ** 30
    print(f"Measuring optimal chunk size to send {data_size/1024/1024} MB through a multiprocessing.Pipe() connection...")
    optimal_chunk_size, optimal_time = find_optimal_chunk_size(data_size)
    if optimal_chunk_size:
        print(f"\nOptimal Chunk Size: {optimal_chunk_size} bytes, Time: {optimal_time:.6f} seconds")
    else:
        print("\nNo optimal chunk size found. All attempts failed.")

# CONCLUSION - Chunk size doesn't seem to matter much? Differences are pretty negligible (on my machine anyway). Also duplex option doesn't seem to make much difference.