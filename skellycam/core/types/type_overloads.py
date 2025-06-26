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

