import threading
import time
from typing import List

import numpy as np

from skellycam.core import CameraId
from skellycam.system.device_detection.camera_device_info import AvailableCameras, CameraDeviceInfo
import logging
import cv2

logger = logging.getLogger(__name__)


def get_available_cameras_opencv() -> AvailableCameras:
    available_cameras = {}
    for port in detect_opencv_ports():
        available_cameras[CameraId(port)] = CameraDeviceInfo.from_opencv_port_number(port)
    return available_cameras


def check_opencv_camera_port_available(port: int, check_images:int=5) -> bool:
    logger.trace(f"Checking if camera on port: {port} is available...")
    cap = cv2.VideoCapture(port)
    try:
        successes = []
        images = []
        durations = []
        for _ in range(check_images):
            tik = time.perf_counter()
            success, image = cap.read()
            if not success:
                logger.trace(f"Failed to grab image from camera on port: {port}")
                return False
            tok = time.perf_counter()
            successes.append(success)
            images.append(image)
            durations.append(tok-tik)

        all_success = all(successes)
        all_images = all([image is not None for image in images])
        if len(durations) == 0:
            raise ValueError("No durations recorded!")
        else:
            mean_duration = sum(durations)/len(durations)
        all_image_diffs = [np.mean(np.abs(images[i].ravel() - images[i+1].ravel())) for i in range(len(images)-1)]
        mean_image_diffs = np.mean(all_image_diffs)
        same_image = mean_image_diffs < 0.01

        if cap.isOpened() and all_success and all_images and mean_duration < 2 and not same_image:
            logger.debug(f"Camera on port: {port} is available: All success: {all_success}, All images: {all_images}, Mean image grab duration: {mean_duration*1000:.3f} (ms), Mean image diffs: {mean_image_diffs:.3f}")
        else:
            logger.trace(f"Camera on port: {port} is not available: All success: {all_success}, All images: {all_images}, Mean duration: {mean_duration*1000:.3f} (ms, if higher than 1.0, this is likely a virtual camera), Mean image diffs: {mean_image_diffs} (if lower than 0.01, this is likely a virtual camera sending identical images)")
            return False
        cap.release()
        return True
    except Exception as e:
        if cap:
            cap.release()
        return False

def detect_opencv_ports(max_ports: int = 20) -> List[int]:
    ports = []
    for port in range(max_ports):
        if check_opencv_camera_port_available(port):
            ports.append(port)

    return ports

if __name__ == "__main__":
    print(get_available_cameras_opencv())
