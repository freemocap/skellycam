import logging
import multiprocessing
from pydantic import BaseModel, Field, SkipValidation, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)




class CameraStatus(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    running: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    connected: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    grabbing_frame: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    closing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    should_close: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    is_paused: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))

    frame_count: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("q",-1))



    @property
    def ready(self) -> bool:
        return all([self.connected.value,
                    self.running.value,
                    not self.should_close.value,
                    not self.closing.value,
                    not self.closed.value,
                    not self.updating.value,
                    not self.is_paused.value,
                    not self.error.value,
                    ]
                    )

    def signal_error(self):
        self.error.value = True
        self.connected.value = False
        self.running.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False

    def signal_closing(self):
        """
        Signal that the camera is closing.
        """
        self.closing.value = True
        self.running.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False
        self.should_close.value = True


class CameraConnection(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    camera_id: CameraIdString
    config: CameraConfig
    status: CameraStatus = Field(default_factory=CameraStatus)

    @classmethod
    def create(cls, config: CameraConfig):
        if not isinstance(config, CameraConfig):
            raise TypeError(f"config must be an instance of CameraConfig, got {type(config)} instead.")
        instance = cls(camera_id=config.camera_id,
                       config=config)
        instance.config = config
        return instance

