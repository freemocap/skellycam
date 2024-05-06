import time
from typing import Dict, Optional, List

import numpy as np
from pydantic import BaseModel, Field

from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload
from skellycam.backend.core.frames.shared_memory import SharedImageMemoryManager


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
                                                           description="A mapping of camera_id to FramePayload")
    shared_memory_image: Dict[CameraId, Optional[int]] = Field(default_factory=dict,
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
               camera_ids: List[CameraId],
               **kwargs):
        utc_ns = time.time_ns()
        perf_ns = time.perf_counter_ns()
        return cls(frames={CameraId(camera_id): None for camera_id in camera_ids},
                   utc_ns_to_perf_ns={"time.time_ns": int(utc_ns), "time.perf_counter_ns": int(perf_ns)},
                   **kwargs
                   )

    @classmethod
    def from_previous(cls, previous: 'MultiFramePayload'):
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns.copy(),
                   )

    @property
    def camera_ids(self) -> List[CameraId]:
        return [CameraId(camera_id) for camera_id in self.frames.keys()]

    def add_shared_memory_image(self, frame: FramePayload, shared_memory_manager: SharedImageMemoryManager):
        self.shared_memory_image[frame.camera_id] = shared_memory_manager.put_image(frame.image)
        self.image_checksums[frame.camera_id] = np.sum(frame.image)

    def hydrate_shared_memory_images(self, shared_memory_manager: SharedImageMemoryManager):
        for camera_id, image_index in self.shared_memory_image.items():
            if image_index is not None:
                self.frames[camera_id].image = shared_memory_manager.get_image(image_index)
