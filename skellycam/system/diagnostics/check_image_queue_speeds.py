import multiprocessing
import time
from typing import Tuple

import numpy as np

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig


def create_fake_image() -> np.ndarray:
    return np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)


def sender(queue: multiprocessing.Queue,
           pipe: multiprocessing.Pipe,
           bytes_pipe: multiprocessing.Pipe,
           iterations: int) -> None:
    image = create_fake_image()
    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        queue.put(image, block=False)
        tok = time.perf_counter_ns()
        durations.append(tok - tik)
    queue.put(None)
    print(f"Average time to send 1080p image down a queue: {sum(durations) / len(durations) / 1e6} ms")

    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        pipe.send(image)
        tok = time.perf_counter_ns()
        durations.append(tok - tik)
    pipe.send(None)
    print(f"Average time to send 1080p image down a pipe: {sum(durations) / len(durations) / 1e6} ms")

    durations = []
    for _ in range(iterations):
        tik = time.perf_counter_ns()
        bytes_pipe.send_bytes(image.tobytes())
        tok = time.perf_counter_ns()
        durations.append(tok - tik)
    bytes_pipe.send_bytes(b'STOP')
    print(f"Average time to send_bytes 1080p image down a pipe: {sum(durations) / len(durations) / 1e6} ms")


def receiver(queue: multiprocessing.Queue,
             pipe: multiprocessing.Pipe,
             bytes_pipe: multiprocessing.Pipe,
             iterations: int) -> None:
    durations = []
    should_continue = True
    while should_continue is not None:
        if not queue.empty():
            tik = time.perf_counter_ns()
            should_continue = queue.get(block=False)
            tok = time.perf_counter_ns()
            durations.append(tok - tik)
        time.sleep(0.01)
    print(f"Average time to recv 1080p image from a queue: {sum(durations) / len(durations) / 1e6} ms\n\n")

    durations = []
    should_continue = True
    while should_continue is not None:
        if pipe.poll():
            tik = time.perf_counter_ns()
            should_continue = pipe.recv()
            tok = time.perf_counter_ns()
            durations.append(tok - tik)
        time.sleep(0.01)

    print(f"Average time to recv 1080p image from a pipe: {sum(durations) / len(durations) / 1e6} ms\n\n")

    durations = []
    should_continue = True
    while should_continue != b'STOP':
        if bytes_pipe.poll():
            tik = time.perf_counter_ns()
            should_continue = bytes_pipe.recv_bytes()
            tok = time.perf_counter_ns()
            durations.append(tok - tik)
        time.sleep(0.01)

    print(f"Average time to recv_bytes 1080p image from a pipe: {sum(durations) / len(durations) / 1e6} ms")


def measure_time(iterations: int = 100) -> Tuple[float, float]:
    queue = multiprocessing.Queue()
    pipe1, pipe2 = multiprocessing.Pipe()
    bytes_pipe1, bytes_pipe2 = multiprocessing.Pipe(duplex=True)
    config = CameraConfig(camera_id=0)

    sender_process = multiprocessing.Process(target=sender, args=(queue,
                                                                  pipe1,
                                                                  bytes_pipe1,
                                                                  iterations))
    receiver_process = multiprocessing.Process(target=receiver, args=(queue,
                                                                      pipe2,
                                                                      bytes_pipe2,
                                                                      iterations))

    start_time = time.perf_counter_ns()

    sender_process.start()
    receiver_process.start()

    sender_process.join()
    receiver_process.join()

    end_time = time.perf_counter_ns()




if __name__ == '__main__':
    measure_time()
    print('Done')
