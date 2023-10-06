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


def update_shared_memory_image(shared_memory_info: Dict[str, Union[str, int]],
                               camera_index: int,
                               exit_event: multiprocessing.Event,
                               rolling_frame_buffer_size: int,
                               number_of_frames_read: multiprocessing.Value):
    shared_memory_name = shared_memory_info["name"]
    shared_memory_dtype = shared_memory_info["data_type"]
    shared_memory_shape = shared_memory_info["shape"]
    logger.info(f"Child Process: {shared_memory_name} - starting")
    camera_capture = cv2.VideoCapture(camera_index)
    existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
    logger.info(f"Child Process: {existing_shared_memory.name} - shared_memory_array shape: {shared_memory_shape}")
    shared_image_array = np.ndarray(shape=shared_memory_shape,
                                    dtype=shared_memory_dtype,
                                    buffer=existing_shared_memory.buf)

    try:

        while not exit_event.is_set():
            logger.debug(f"Child Process: {existing_shared_memory.name} - reading new frame from camera")
            read_successful, frame = camera_capture.read()
            if read_successful:
                number_of_frames_read.value += 1
                logger.debug(f"Child Process: {existing_shared_memory.name} - read frame {number_of_frames_read.value}")
                shared_image_array[number_of_frames_read.value % rolling_frame_buffer_size] = frame
                logger.debug(f"Child Process: {existing_shared_memory.name} - wrote frame {number_of_frames_read.value}")
            else:
                logger.error(f"Child Process: {existing_shared_memory.name} - failed to read frame!!")

    except Exception as e:
        logger.error(f"Child Process: {existing_shared_memory.name} - {e}")
        logger.exception(e)
    finally:
        logger.info(f"Child Process: {existing_shared_memory.name} - releasing camera")
        camera_capture.release()
        if not exit_event.is_set():
            logger.error(f"Child Process: {existing_shared_memory.name} exited unexpectedly")
            exit(333)


def parent_function():
    exit_code = 0
    initial_image = get_initial_image()

    logger.info(f"Initial frame shape: {initial_image.shape}")
    rolling_frame_buffer_size = 100
    image_shape = initial_image.shape
    initial_image_array = np.zeros(shape=(rolling_frame_buffer_size, image_shape[0], image_shape[1], image_shape[2]),
                                   dtype=initial_image.dtype)
    number_of_bytes_needed = initial_image_array.nbytes
    shared_memory_block = shared_memory.SharedMemory(create=True, size=number_of_bytes_needed)
    shared_image_array = np.ndarray(initial_image_array.shape, dtype=initial_image_array.dtype,
                                    buffer=shared_memory_block.buf)
    shared_image_array[:] = initial_image_array[:]
    logger.info(f"Created shared memory block: {shared_memory_block.name} - {shared_image_array.shape}")

    logger.info("Starting child process")
    exit_event = multiprocessing.Event()
    shared_memory_info = {"name": shared_memory_block.name,
                          "data_type": shared_image_array.dtype,
                          "shape": shared_image_array.shape}
    # multiprocess.Value integer to keep track of how many frames have been read from the camera
    number_of_frames_read = multiprocessing.Value('i', 0)
    child_process = Process(target=update_shared_memory_image,
                            args=(shared_memory_info, 0, exit_event, rolling_frame_buffer_size, number_of_frames_read))
    child_process.start()

    try:
        number_frame_shown = -1
        while not exit_event.is_set():
            if number_frame_shown >= number_of_frames_read.value:
                time.sleep(0.01)
                continue
            number_frame_shown += 1
            image_to_display = shared_image_array[number_frame_shown % rolling_frame_buffer_size]
            logger.debug(f"Main Process: {image_to_display.shape} - trying to show image")
            cv2.imshow("Shared Memory Camera - `q` to quit", image_to_display)
            # exit loop on Q or ESC
            if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
                exit_event.set()

    except Exception as e:
        logger.error(f"Main Process: {e}")
        logger.exception(e)
    finally:
        if child_process.is_alive():
            exit_code = 222
            exit_event.set()
        logger.info("Main Process: Closing child process...")
        child_process.join()
        logger.info("Main Process: Closing shared memory block...")
        shared_memory_block.close()
        logger.info("Main Process: Unlinking shared memory block...")
        shared_memory_block.unlink()
        logger.info("Main Process: Exiting...")
        exit(exit_code)


def get_initial_image():
    logger.info("Creating VideoCapture object to get initial frame")
    video_capture = cv2.VideoCapture(0)  # Assuming camera_index as 0.
    if not video_capture.isOpened():
        logger.error("Could not open video capture device")
        exit(123)
    read_successful, initial_image = video_capture.read()
    if not read_successful:
        logger.error("Could not read initial frame")
        exit(342)
    video_capture.release()
    return initial_image


if __name__ == '__main__':
    parent_function()
