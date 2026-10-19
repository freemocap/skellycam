"""Serializable camera startup failures shared by workers and their parent."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraSetupFailure:
    camera_id: str
    phase: str
    exception_type: str
    message: str

    def __str__(self) -> str:
        return (f"Camera {self.camera_id} failed during {self.phase}: "
                f"{self.exception_type}: {self.message}")


class CameraSetupFailedException(RuntimeError):
    """Recoverable group startup failure; must not kill the whole backend."""
