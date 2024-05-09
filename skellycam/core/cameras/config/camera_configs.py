from typing import Dict

from pydantic import RootModel

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core import CameraId


class CameraConfigs(RootModel):
    root: Dict[CameraId, CameraConfig] = {CameraId(0): CameraConfig(camera_id=CameraId(0))}


    def __str__(self):
        """
        pretty print the camera configs
        """
        out_str = f""
        for camera_id, config in self.root.items():
            out_str += f"Camera {camera_id}:\n{config}\n"
        return out_str

    def __getitem__(self, key):
        return self.root[CameraId(key)]

    def __setitem__(self, key, value):
        self.root[CameraId(key)] = value

    def __delitem__(self, key):
        del self.root[CameraId(key)]

    def __iter__(self):
        return iter(self.root)

    def __len__(self):
        return len(self.root)

    def __contains__(self, item):
        return item in self.root

    def __eq__(self, other):
        return self.root == other.root

    def keys(self):
        return self.root.keys()

    def values(self):
        return self.root.values()

    def items(self):
        return self.root.items()

