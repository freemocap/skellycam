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
        return out_str


if __name__ == "__main__":
    print(CameraConfigs())
