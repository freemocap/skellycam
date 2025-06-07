import logging
import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)



@dataclass
class CameraStatus:
    running: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))
    connected: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))
    grabbing_frame: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))
    frame_count: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("q",-1))

    closing: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))
    closed: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))

    paused: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))

    updating: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))
    error: multiprocessing.Value("b", False) = field(default_factory=lambda: multiprocessing.Value("b", False))



    @property
    def ready(self) -> bool:
        return all([self.connected.value,
                    self.running.value,
                    not self.grabbing_frame.value,
                    not self.closing.value,
                    not self.closed.value,
                    not self.updating.value,
                    not self.paused.value,
                    not self.error.value,
                    ]
                    )
    def signal_error(self):
        self.error.value = True
        self.connected.value = False
        self.running.value = False
        self.grabbing_frame.value = False
        self.paused.value = False

    def signal_closing(self):
        """
        Signal that the camera is closing.
        """
        self.closing.value = True
        self.running.value = False
        self.grabbing_frame.value = False
        self.paused.value = False

@dataclass
class CameraConnection:
    camera_id: CameraIdString
    config: CameraConfig
    status: CameraStatus = field(default_factory=CameraStatus)

    @classmethod
    def create(cls, config: CameraConfig):
        if not isinstance(config, CameraConfig):
            raise TypeError(f"config must be an instance of CameraConfig, got {type(config)} instead.")
        instance = cls(camera_id=config.camera_id,
                       config=config)
        instance.config = config
        return instance

