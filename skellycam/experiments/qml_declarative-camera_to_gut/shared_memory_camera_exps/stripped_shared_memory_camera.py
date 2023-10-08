import logging
import multiprocessing
import time
from multiprocessing import shared_memory, Process
from typing import Dict, Union

import cv2
import numpy as np

from skellycam import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

CHOSEN_RESOLUTION = (1280, 720)


def camera_loop(shared_memory_info: Dict[str, Union[str, int]],
                camera_index: int,
                exit_event: multiprocessing.Event,
                rolling_frame_buffer_size: int,
                current_buffer_index: multiprocessing.Value,
                resolution: tuple = CHOSEN_RESOLUTION):
    shared_memory_name = shared_memory_info["name"]
    shared_memory_dtype = shared_memory_info["data_type"]
    shared_memory_shape = shared_memory_info["shape"]
    camera_capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    camera_capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    camera_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
    shared_image_array = np.ndarray(shape=shared_memory_shape,
                                    dtype=shared_memory_dtype,
                                    buffer=existing_shared_memory.buf)

    current_frame_number = -1
    while not exit_event.is_set():
        tik = time.perf_counter()
        read_successful, image = camera_capture.read()
        tok = time.perf_counter()
        #print with 3 precision
        print(f"grab duration: {(tok - tik) * 1000:.3f} ms")
        current_frame_number += 1
        current_buffer_index.value = current_frame_number % rolling_frame_buffer_size
        shared_image_array[current_buffer_index.value] = image


def parent_function():
    initial_image = get_initial_image()
    rolling_frame_buffer_size = 30
    image_shape = initial_image.shape
    initial_image_array = np.zeros(shape=(rolling_frame_buffer_size, image_shape[0], image_shape[1], image_shape[2]),
                                   dtype=initial_image.dtype)
    number_of_bytes_needed = initial_image_array.nbytes
    shared_memory_block = shared_memory.SharedMemory(create=True, size=number_of_bytes_needed)
    shared_image_array = np.ndarray(initial_image_array.shape, dtype=initial_image_array.dtype,
                                    buffer=shared_memory_block.buf)
    shared_image_array[:] = initial_image_array[:]

    logger.info("Starting child process")
    exit_event = multiprocessing.Event()
    shared_memory_info = {"name": shared_memory_block.name,
                          "data_type": shared_image_array.dtype,
                          "shape": shared_image_array.shape}
    # multiprocess.Value integer to keep track of how many frames have been read from the camera
    current_buffer_index = multiprocessing.Value('i', 0)
    child_process = Process(target=camera_loop,
                            args=(shared_memory_info, 0, exit_event, rolling_frame_buffer_size, current_buffer_index))
    child_process.start()

    number_frame_shown = -1
    images_to_show = []
    previous_frame_buffer_index = 0
    while not exit_event.is_set():
        current_frame_buffer_copy = np.copy(current_buffer_index.value)
        current_frame_buffer_copy -= 1
        if current_frame_buffer_copy < 0:
            current_frame_buffer_copy = rolling_frame_buffer_size - 1
        if previous_frame_buffer_index == current_frame_buffer_copy:
            time.sleep(0.001)
            continue
        else:
            number_frame_shown += 1
            images_to_show.append(shared_image_array[current_frame_buffer_copy].copy())
            previous_frame_buffer_index = current_frame_buffer_copy

        if len(images_to_show) > 0:
            image_to_display = images_to_show.pop(0)
            cv2.imshow("Shared Memory Camera - `q` to quit", image_to_display)
        # exit loop on Q or ESC
        if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
            exit_event.set()

    logger.info("Cleaning up")
    child_process.join()
    shared_memory_block.close()
    shared_memory_block.unlink()


def get_initial_image(resolution: tuple = CHOSEN_RESOLUTION):
    video_capture = cv2.VideoCapture(0)  # Assuming camera_index as 0.
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    read_successful, initial_image = video_capture.read()
    video_capture.release()
    return initial_image


if __name__ == '__main__':
    parent_function()
