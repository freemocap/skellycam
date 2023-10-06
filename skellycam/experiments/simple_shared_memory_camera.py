import logging
import multiprocessing
import time

import numpy as np
import cv2
from multiprocessing import shared_memory, Process

from skellycam import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

def update_shared_memory_image(shared_memory_name: str,
                               camera_index: int,
                               exit_event: multiprocessing.Event):
    logger.info(f"Child Process: {shared_memory_name} - starting")
    camera_capture = cv2.VideoCapture(camera_index)
    existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
    read_successful, frame = camera_capture.read()
    if not read_successful:
        logger.error(f"Child Process: {existing_shared_memory.name} - could not read initial frame")
        exit(1)
    logger.info(f"Child Process: {existing_shared_memory.name} - initial frame shape: {frame.shape}")
    shared_image_frame = np.ndarray(frame.shape, dtype=frame.dtype, buffer=existing_shared_memory.buf)
    shared_image_frame[:] = frame[:]

    try:
        while not exit_event.is_set():
            logger.debug(f"Child Process: {existing_shared_memory.name} - reading new frame from camera")
            read_successful, frame = camera_capture.read()
            if not read_successful:
                break
            shared_image_frame[:] = frame[:]

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
    logger.info("Creating VideoCapture object to get initial frame")
    video_capture = cv2.VideoCapture(0)  # Assuming camera_index as 0.
    if not video_capture.isOpened():
        logger.error("Could not open video capture device")
        exit(123)
    read_successful, initial_frame = video_capture.read()
    if not read_successful:
        logger.error("Could not read initial frame")
        exit(342)
    logger.info(f"Initial frame shape: {initial_frame.shape}")
    shared_memory_block = shared_memory.SharedMemory(create=True, size=initial_frame.nbytes)
    shared_image_frame = np.ndarray(initial_frame.shape, dtype=initial_frame.dtype, buffer=shared_memory_block.buf)
    shared_image_frame[:] = initial_frame[:]
    logger.info(f"Created shared memory block: {shared_memory_block.name} - {shared_image_frame.shape}")
    video_capture.release()

    logger.info("Starting child process")
    exit_event = multiprocessing.Event()
    child_process = Process(target=update_shared_memory_image, args=(shared_memory_block.name, 0, exit_event))
    child_process.start()
    try:
        while not exit_event.is_set():

            logger.debug(f"Main Process: {shared_image_frame.shape} - trying to show image")
            time.sleep(0.033)
            cv2.imshow("Shared Memory Camera - `q` to quit", shared_image_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
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
if __name__ == '__main__':
    parent_function()
