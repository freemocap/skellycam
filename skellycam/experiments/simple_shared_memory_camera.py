import logging
import multiprocessing
import time
from multiprocessing import shared_memory, Process
from typing import Dict, Union, Tuple

import cv2
import numpy as np

from skellycam import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

RESOLUTION_WIDTH = 1280
RESOLUTION_HEIGHT = 720


def child_camera_process(shared_memory_info: Dict[str, Union[str, int]],
                         camera_index: int,
                         exit_event: multiprocessing.Event,
                         rolling_frame_buffer_size: int,
                         number_of_frames_read: multiprocessing.Value):

    logger.info(f"Child Process: starting...")
    camera_capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    camera_capture.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_WIDTH)
    camera_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_HEIGHT)

    shared_image_array = create_shared_memory_array(memory_name=shared_memory_info["name"],
                                                    shape=shared_memory_info["shape"],
                                                    data_type=shared_memory_info["data_type"])

    try:
        while not exit_event.is_set():
            read_successful, frame = camera_capture.read()
            if read_successful:
                number_of_frames_read.value += 1
                shared_image_array[number_of_frames_read.value % rolling_frame_buffer_size] = frame
            else:
                logger.error(f"Child Process failed to read frame!!")

    except Exception as e:
        logger.error(f"Error in Child Process: - {e} \n\n {e.__traceback__}")
        logger.exception(e)
    finally:
        logger.info(f"Child Process - releasing camera {camera_index}")
        camera_capture.release()
        if not exit_event.is_set():
            logger.error(f"Child Process exited unexpectedly :(")
            exit(333)


def create_shared_memory_block(shape: Tuple[int, int, int, int], # (rolling_frame_buffer_size, height, width, color_channels)
                               data_type: np.dtype):
    initial_image_array = np.zeros(shape=shape,
                                   dtype=data_type)
    number_of_bytes_needed = initial_image_array.nbytes
    shared_memory_block = shared_memory.SharedMemory(create=True, size=number_of_bytes_needed)
    logger.info(
        f"Created shared memory block: {shared_memory_block.name} - shape: {initial_image_array.shape} - data type: {initial_image_array.dtype}")
    return shared_memory_block


def create_shared_memory_array(memory_name, shape, data_type):
    shared_memory_block = shared_memory.SharedMemory(name=memory_name)
    shared_image_array = np.ndarray(shape=shape,
                                    dtype=data_type,
                                    buffer=shared_memory_block.buf)
    return shared_image_array
def parent_function():
    exit_code = 0
    initial_image = get_initial_image()
    logger.info(f"Initial frame shape: {initial_image.shape}")
    rolling_buffer_size = 100

    share_array_shape = (rolling_buffer_size, initial_image.shape[0], initial_image.shape[1], initial_image.shape[2])
    shared_memory_block = create_shared_memory_block(shape=share_array_shape,
                                                     data_type=initial_image.dtype)
    shared_image_array = create_shared_memory_array(memory_name=shared_memory_block.name,
                                                    shape=share_array_shape,
                                                    data_type=initial_image.dtype)

    logger.info("Starting child process")
    exit_event = multiprocessing.Event()
    shared_memory_info = {"name": shared_memory_block.name,
                          "data_type": shared_image_array.dtype,
                          "shape": shared_image_array.shape}
    # multiprocess.Value integer to keep track of how many frames have been read from the camera
    number_of_frames_read = multiprocessing.Value('i', 0)
    child_process = Process(target=child_camera_process,
                            args=(shared_memory_info, 0, exit_event, rolling_buffer_size, number_of_frames_read))
    child_process.start()

    try:
        number_frame_shown = -1
        while not exit_event.is_set():
            if number_frame_shown >= number_of_frames_read.value:
                time.sleep(0.001)
                continue
            number_frame_shown += 1
            image_to_display = shared_image_array[
                number_frame_shown % rolling_buffer_size].copy()  # copying is non-blocking
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
        child_process.join()
        exit_code = child_process.exitcode
        shared_memory_block.close()
        shared_memory_block.unlink()
        logger.info("Main Process: Exiting...")
        exit(exit_code)


def get_initial_image():
    logger.info("Creating VideoCapture object to get initial frame")
    # a RESOLUTION_WIDTH by RESOLUTION_HEIGHT image
    video_capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_WIDTH)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_HEIGHT)
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
