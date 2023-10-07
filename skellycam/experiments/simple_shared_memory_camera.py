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

RESOLUTION_1080P = (1920, 1080)
RESOLUTION_720P = (1280, 720)
RESOLUTION_480P = (640, 480)

CHOSEN_RESOLUTION = RESOLUTION_480P


def camera_loop(shared_memory_info: Dict[str, Union[str, int]],
                camera_index: int,
                exit_event: multiprocessing.Event,
                rolling_frame_buffer_size: int,
                current_buffer_index: multiprocessing.Value,
                resolution: tuple = CHOSEN_RESOLUTION):
    shared_memory_name = shared_memory_info["name"]
    shared_memory_dtype = shared_memory_info["data_type"]
    shared_memory_shape = shared_memory_info["shape"]
    logger.info(f"Child Process: {shared_memory_name} - starting")
    camera_capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    camera_capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    camera_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
    logger.info(f"Child Process: {existing_shared_memory.name} - shared_memory_array shape: {shared_memory_shape}")
    shared_image_array = np.ndarray(shape=shared_memory_shape,
                                    dtype=shared_memory_dtype,
                                    buffer=existing_shared_memory.buf)

    current_frame_number = -1
    try:
        previous_frame_time = time.perf_counter()
        while not exit_event.is_set():
            logger.debug(f"Child Process: {existing_shared_memory.name} - reading new image from camera")

            pre_grab_tik = time.perf_counter()
            read_successful, image = camera_capture.read()
            current_frame_time = time.perf_counter()
            grab_duration_ms = (current_frame_time - pre_grab_tik) * 1000
            since_last_frame_ms = (current_frame_time - previous_frame_time) * 1000
            previous_frame_time = current_frame_time

            if read_successful:
                current_frame_number += 1
                current_buffer_index.value = current_frame_number % rolling_frame_buffer_size
                logger.debug(f"Child Process: {existing_shared_memory.name} - read image {current_buffer_index.value}")

                logger.debug(f"Child Process: {existing_shared_memory.name} - wrote image {current_buffer_index.value}")

                annotated_image = annotate_image(image=image,
                                                 frame_number=current_frame_number,
                                                 current_buffer_index=current_buffer_index.value,
                                                 grab_duration_ms=grab_duration_ms,
                                                 since_last_frame_ms=since_last_frame_ms,
                                                 resolution=resolution,
                                                 rolling_frame_buffer_size=rolling_frame_buffer_size)
                shared_image_array[current_buffer_index.value] = annotated_image
            else:
                logger.error(f"Child Process: {existing_shared_memory.name} - failed to read image!!")

    except Exception as e:
        logger.error(f"Child Process: {existing_shared_memory.name} - {e}")
        logger.exception(e)
    finally:
        logger.info(f"Child Process: {existing_shared_memory.name} - releasing camera")
        camera_capture.release()
        if not exit_event.is_set():
            logger.error(f"Child Process: {existing_shared_memory.name} exited unexpectedly")
            exit(333)


def annotate_image(image: np.ndarray,
                   frame_number: int,
                   current_buffer_index: int,
                   grab_duration_ms: float,
                   since_last_frame_ms: float,
                   resolution: tuple,
                   rolling_frame_buffer_size: int):
    tik = time.perf_counter()
    annotated_image = image.copy()
    annotated_image = cv2.putText(annotated_image, f"Frame#: {frame_number}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                  1, (0, 0, 255), 2)
    annotated_image = cv2.putText(annotated_image, f"Resolution: {resolution}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                  (0, 0, 255), 2)
    annotated_image = cv2.putText(annotated_image, f"Grab Duration: {grab_duration_ms:.2f} ms", (10, 90),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    annotated_image = cv2.putText(annotated_image, f"Frame Duration: {since_last_frame_ms:.2f} ms", (10, 120),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    annotated_image = cv2.circle(annotated_image, (
        int(current_buffer_index / rolling_frame_buffer_size * resolution[0]), resolution[1] - 10), 5, (0, 0, 255), -1)

    tok = time.perf_counter()
    annotation_duration_ms = (tok - tik) * 1000
    annotated_image = cv2.putText(annotated_image, f"Annotation Duration: {annotation_duration_ms:.2f} ms", (10, 150),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    return annotated_image


def parent_function():
    exit_code = 0
    initial_image = get_initial_image()

    logger.info(f"Initial image shape: {initial_image.shape}")
    rolling_frame_buffer_size = 30
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
    current_buffer_index = multiprocessing.Value('i', 0)
    child_process = Process(target=camera_loop,
                            args=(shared_memory_info, 0, exit_event, rolling_frame_buffer_size, current_buffer_index))
    child_process.start()

    try:
        number_frame_shown = -1
        images_to_show = []
        previous_frame_buffer_index = 0
        while not exit_event.is_set():
            current_frame_buffer_copy = np.copy(current_buffer_index.value)
            current_frame_buffer_copy -= 1
            if current_frame_buffer_copy < 0:
                current_frame_buffer_copy = rolling_frame_buffer_size - 1
            if previous_frame_buffer_index == current_frame_buffer_copy:
                time.sleep(0.01)
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


def get_initial_image(resolution: tuple = CHOSEN_RESOLUTION):
    logger.info("Creating VideoCapture object to get initial image")
    video_capture = cv2.VideoCapture(0)  # Assuming camera_index as 0.
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    if not video_capture.isOpened():
        logger.error("Could not open video capture device")
        exit(123)
    read_successful, initial_image = video_capture.read()
    if not read_successful:
        logger.error("Could not read initial image")
        exit(342)
    video_capture.release()
    return initial_image


if __name__ == '__main__':
    parent_function()
