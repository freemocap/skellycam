import multiprocessing
import time
from distutils.command.config import config
from typing import Tuple

import numpy as np
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig

def create_fake_image() -> np.ndarray:
    """Creates a fake 1080p image using NumPy.

    Returns
    -------
    np.ndarray
        A 3D array representing a fake 1080p image with random pixel values.
    """
    return np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)


def sender(queue: multiprocessing.Queue,
           pipe: multiprocessing.Pipe,
           iterations: int) -> None:
    """Sends a fake 1080p image to the receiver process multiple times.

    Parameters
    ----------
    queue : multiprocessing.Queue
        The queue used to send the image between processes.
    iterations : int
        The number of times to send the image.
    """
    image = create_fake_image()
    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        queue.put(image)
        tok = time.perf_counter_ns()
        durations.append(tok - tik)
    print(f"Average time to send 1080p image down a queue: {sum(durations) / len(durations) / 1e6} ms")

    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        pipe.send(image)
        tok = time.perf_counter_ns()
        durations.append(tok - tik)

    print(f"Average time to send 1080p image down a pipe: {sum(durations) / len(durations) / 1e6} ms")

    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        pipe.send_bytes(image)
        tok = time.perf_counter_ns()
        durations.append(tok - tik)

    print(f"Average time to send_bytes 1080p image down a pipe: {sum(durations) / len(durations) / 1e6} ms")

def receiver(queue: multiprocessing.Queue,
             pipe: multiprocessing.Pipe,
             iterations: int) -> None:
    """Receives a fake 1080p image from the sender process multiple times.

    Parameters
    ----------
    queue : multiprocessing.Queue
        The queue used to receive the image between processes.
    iterations : int
        The number of times to receive the image.
    """
    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        _ = queue.get()
        tok = time.perf_counter_ns()
        durations.append(tok - tik)
    print(f"Average time to recv 1080p image from a queue: {sum(durations) / len(durations) / 1e6} ms\n\n")

    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        _ = pipe.recv()
        tok = time.perf_counter_ns()
        durations.append(tok - tik)

    print(f"Average time to recv 1080p image from a pipe: {sum(durations) / len(durations) / 1e6} ms")

    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        _ = pipe.recv_bytes()
        tok = time.perf_counter_ns()
        durations.append(tok - tik)

    print(f"Average time to recv_bytes 1080p image from a pipe: {sum(durations) / len(durations) / 1e6} ms")


def measure_time(iterations: int = 100) -> Tuple[float, float]:
    """Measures the time taken to send and receive a 1080p image between two processes.

    Parameters
    ----------
    iterations : int, optional
        The number of times to send and receive the image, by default 100.

    Returns
    -------
    Tuple[float, float]
        The time taken to send and receive the image in seconds.
    """
    queue = multiprocessing.Queue()
    pipe1, pipe2 = multiprocessing.Pipe()
    config = CameraConfig(camera_id=0)

    sender_process = multiprocessing.Process(target=sender, args=(queue, pipe1, iterations))
    receiver_process = multiprocessing.Process(target=receiver, args=(queue, pipe2, iterations))

    start_time = time.perf_counter_ns()

    sender_process.start()
    receiver_process.start()

    sender_process.join()
    receiver_process.join()

    end_time = time.perf_counter_ns()

    total_time = end_time - start_time / 1e9
    avg_time_per_iteration = (total_time / iterations )/ 1e9

    return total_time, avg_time_per_iteration


if __name__ == '__main__':
    total_time, avg_time = measure_time()
    print(f"Total time for sending and receiving: {total_time:.6f} seconds")
    print(f"Average time per send/receive: {avg_time:.6f} seconds")
