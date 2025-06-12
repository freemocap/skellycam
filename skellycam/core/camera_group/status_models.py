import logging
import multiprocessing

from pydantic import BaseModel, Field, SkipValidation, ConfigDict

logger = logging.getLogger(__name__)


class CameraStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True
                              )
    running: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    connected: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    grabbing_frame: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    closing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    should_close: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    is_paused: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))

    frame_count: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("q", -1))

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
                    ])

    def signal_error(self):
        self.error.value = True
        self.connected.value = False
        self.running.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False

    def signal_closing(self):
        self.closing.value = True
        self.running.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False
        self.should_close.value = True


class RecordingManagerStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    is_recording_frames_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    should_record: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    is_running_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    finishing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    is_paused_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    total_frames_published: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('Q', 0))
    number_frames_published_this_cycle: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('i', 0))

    @property
    def recording(self) -> bool:
        return self.is_recording_frames_flag.value and self.should_record.value


