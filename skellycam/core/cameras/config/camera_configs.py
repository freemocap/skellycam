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

    def __getitem__(self, item):
        return self.root[item]

    def __setitem__(self, key, value):
        self.root[CameraId(key)] = value

    def __delitem__(self, key):
        del self.root[key]

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


if __name__ == "__main__":
    configs = CameraConfigs()
    configs[1] = CameraConfig(camera_id=CameraId(1))
    configs[2] = CameraConfig(camera_id=CameraId(2))
    print(configs)
