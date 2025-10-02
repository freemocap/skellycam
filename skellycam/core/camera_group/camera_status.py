import multiprocessing
from dataclasses import dataclass, field


@dataclass
class CameraStatus:
    connected: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    grabbing_frame: multiprocessing.Value = field(
        default_factory=lambda: multiprocessing.Value("b", False))
    closing: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    closed: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    recording_in_progress: multiprocessing.Value = field(
        default_factory=lambda: multiprocessing.Value("b", False))
    is_recording_frame: multiprocessing.Value = field(
        default_factory=lambda: multiprocessing.Value("b", False))
    should_pause: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    should_close: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    is_paused: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    updating: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    error: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))

    frame_count: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("q", -1))

    @property
    def ready(self) -> bool:
        return all([self.connected.value,
                    not self.should_pause.value,
                    not self.should_close.value,
                    not self.closing.value,
                    not self.closed.value,
                    not self.updating.value,
                    not self.error.value,
                    ])

    def signal_error(self):
        self.error.value = True
        self.connected.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False
        self.should_pause.value = False


    def signal_closing(self):
        self.closing.value = True
        self.grabbing_frame.value = False
        self.is_paused.value = False
        self.should_pause.value = False
        self.connected.value = False
        self.updating.value = False
        self.recording_in_progress.value = False
        self.is_recording_frame.value = False
        self.error.value = False

