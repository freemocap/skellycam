import enum
import multiprocessing
import threading

import numpy as np
from pydantic import SkipValidation

CameraIdString = str
CameraGroupIdString = str
CameraNameString = str
SharedMemoryName = str
CameraIndexInt = int
CameraBackendInt = int  # OpenCV backend ID, e.g., cv2.CAP_ANY, cv2.CAP_MSMF,  cv2.CAP_DSHOW, etc.
CameraBackendNameString = str  # Name of the backend, e.g., "MSMF", "DShow", etc.
CameraVendorIdInt = int  # Vendor ID of the camera, e.g., 0x046D for Logitech
CameraProductIdInt = int  # Product ID of the camera, e.g., 0x0825 for Logitech C920
CameraDevicePathString = str  # Path to the camera device, e.g., "/dev/video0" on Linux or "COM3"/ on Windows
FrameNumberInt = int
Base64JPEGImage = str  # Base64 encoded JPEG image
RecordingManagerIdString = str
TopicSubscriptionQueue = SkipValidation[multiprocessing.Queue]
TopicPublicationQueue = SkipValidation[multiprocessing.Queue]

WorkerType = SkipValidation[threading.Thread | multiprocessing.Process]

IMAGE_DATA_DTYPE = np.uint8
BYTES_PER_MONO_PIXEL = np.dtype(IMAGE_DATA_DTYPE).itemsize

class WorkerStrategy(enum.Enum):
    THREAD = threading.Thread
    PROCESS = multiprocessing.Process

