from typing import Dict

from pydantic import model_validator, RootModel

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.detection.camera_id import CameraId


class CameraConfigs(RootModel):
    root: Dict[CameraId, CameraConfig] = {CameraId(0): CameraConfig(camera_id=CameraId(0))}

    def __str__(self):
        """
        pretty print the camera configs
        """
        out_str = f""
        for camera_id, config in self.root.items():
            out_str += f"Camera {camera_id}:\n"
            out_str += "\t" + str(config).replace("\n", "\n\t")
            out_str += "\n"
        # remove the last newline
        out_str = out_str[:-3]
        return out_str

    def __getitem__(self, item):
        return self.root[item]

    def __setitem__(self, key, value):
        self.root[key] = value

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


if __name__ == "__main__":
    configs = CameraConfigs()
    configs[1] = CameraConfig(camera_id=CameraId(1))
    print(configs)
