from typing import Dict

from pydantic import BaseModel

from skellycam.core import CameraId


class SharedMemoryNames(BaseModel):
    image_shm_name: str
    metadata_shm_name: str


GroupSharedMemoryNames = Dict[CameraId, SharedMemoryNames]
