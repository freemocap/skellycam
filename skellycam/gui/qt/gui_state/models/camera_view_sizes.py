from typing import Dict

from pydantic import BaseModel

from skellycam.core import CameraId


class CameraViewSizes(BaseModel):
    sizes: Dict[CameraId, Dict[str, int]] = {}
    epsilon: int = 50  # pixels differences less than this are considered equal

    def __eq__(self, other):
        if not isinstance(other, CameraViewSizes):
            return False
        if len(self.sizes) != len(other.sizes):
            return False
        for camera_id, view_size in self.sizes.items():
            if camera_id not in other.sizes:
                return False
            for key, value in view_size.items():
                if key not in other.sizes[camera_id]:
                    return False
                if abs(value - other.sizes[camera_id][key]) > self.epsilon:
                    return False
        return True

    def too_small(self) -> bool:
        # returns True if any view size is less than threshold
        for camera_id, view_size in self.sizes.items():
            if view_size["width"] < self.epsilon or view_size["height"] < self.epsilon:
                return True
