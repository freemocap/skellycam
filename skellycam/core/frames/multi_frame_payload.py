import time
from typing import Dict, Optional, List

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.device_detection.camera_id import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.shared_image_memory import SharedImageMemoryManager


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
                                                           description="A mapping of camera_id to FramePayload")
    shared_memory_index: Dict[CameraId, Optional[int]] = Field(default_factory=dict,
                                                               description="A mapping of camera_id to and index in the shared memory manager")
    image_checksums: Dict[CameraId, int] = Field(default_factory=dict,
                                                 description="The sum of the pixel values of the image, to verify integrity after shared memory hydration")
    utc_ns_to_perf_ns: Dict[str, int] = Field(
        description="A mapping of `time.time_ns()` to `time.perf_counter_ns()` "
                    "to allow conversion of `time.perf_counter_ns()`'s arbitrary "
                    "time base to unix time")
    logs: List[str] = Field(default_factory=list,
                            description="Lifecycle events for this payload, "
                                        "format: f'{event_name}:{perf_counter_ns}'")
    multi_frame_number: int = 0

    @classmethod
    def create(cls,
               **kwargs):
        utc_ns = time.time_ns()
        perf_ns = time.perf_counter_ns()
        return cls(frames={},
                   utc_ns_to_perf_ns={"time.time_ns": int(utc_ns), "time.perf_counter_ns": int(perf_ns)},
                   logs=[f"created:{perf_ns}"],
                   **kwargs
                   )

    @classmethod
    def from_previous(cls, previous: 'MultiFramePayload'):
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns.copy(),
                   logs=[f"created_from_previous:{time.perf_counter_ns()}"]
                   )

    @property
    def camera_ids(self) -> List[CameraId]:
        return [CameraId(camera_id) for camera_id in self.frames.keys()]

    async def add_shared_memory_image(self,
                                      frame: FramePayload,
                                      shared_memory_manager: SharedImageMemoryManager):
        tik = time.perf_counter_ns()
        self.shared_memory_index[frame.camera_id] = shared_memory_manager.put_image(frame.image)
        self.image_checksums[frame.camera_id] = np.sum(frame.image)
        elapsed = time.perf_counter_ns() - tik
        self.add_log(f"after_adding_shared_memory_image_for_camera_{frame.camera_id}_took_{elapsed}ns")

    def hydrate_shared_memory_images(self, shared_memory_manager: SharedImageMemoryManager):
        for camera_id, frame in self.frames.items():
            if frame is not None:
                tik = time.perf_counter_ns()
                self.frames[camera_id].image = shared_memory_manager.get_image(self.shared_memory_index[camera_id])
                elapsed = time.perf_counter_ns() - tik
                self.add_log(f"shared_memory_image_for_camera_{camera_id}_took_{elapsed}ns")
                self._validate_image(camera_id)

    def _validate_image(self, camera_id):
        self.add_log(f"validate_image_for_camera_{camera_id}")
        if self.frames[camera_id].image is None:
            raise ValueError(f"Image is None for camera_id: {camera_id}")
        if self.frames[camera_id].image.shape != self.frames[camera_id].image_shape:
            raise ValueError(f"Image shape mismatch for camera_id: {camera_id} - "
                             f"Expected: {self.frames[camera_id].image_shape}, "
                             f"Actual: {self.frames[camera_id].image.shape}")
        if self.frames[camera_id].image.dtype != self.frames[camera_id].image_dtype:
            raise ValueError(f"Image dtype mismatch for camera_id: {camera_id} - "
                             f"Expected: {self.frames[camera_id].image_dtype}, "
                             f"Actual: {self.frames[camera_id].image.dtype}")

        if np.sum(self.frames[camera_id].image) != self.image_checksums[camera_id]:
            raise ValueError(f"Image checksum mismatch for camera_id: {camera_id} - "
                             f"Expected: {self.image_checksums[camera_id]}, "
                             f"Actual: {np.sum(self.frames[camera_id].image)}")

    def add_log(self, log: str):
        self.logs.append(f"{log}:{time.perf_counter_ns()}")
