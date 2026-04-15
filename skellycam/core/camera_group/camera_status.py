import multiprocessing
from multiprocessing.sharedctypes import Synchronized
from dataclasses import dataclass, field

# TODO - We should rebuild the camera as a state machine with finite defined states and defined legal transitions from one state to the other.
@dataclass
class CameraStatus:
    connected: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    grabbing_frame: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    closing: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    closed: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    recording_in_progress: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    is_recording_frame: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    should_pause: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    should_close: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    is_paused: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    updating: Synchronized = field(default_factory=lambda: Synchronized("b", False))
    error: Synchronized = field(default_factory=lambda: Synchronized("b", False))

    frame_count: Synchronized = field(default_factory=lambda: Synchronized("q", -1))

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

    def serialize(self):
        return {
            "connected": self.connected.value,
            "closed": self.closed.value,
            "recording_in_progress": self.recording_in_progress.value,
            "is_paused": self.is_paused.value,
            "error": self.error.value,
        }
