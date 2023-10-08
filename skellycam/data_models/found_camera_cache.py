from typing import List

from pydantic import BaseModel


class FoundCameraCache(BaseModel):
    number_of_cameras_found: int
    cameras_found_list: List[str]

    @property
    def as_camera_list(self):
        return [cam for cam in self.cameras_found_list]
