class CameraStateConflict(ValueError):
    """A requested camera operation conflicts with an active recording."""


class CameraConnectionCancelled(RuntimeError):
    """The group stopped before this camera finished connecting."""


class CameraStartFailed(RuntimeError):
    """Cameras could not start; the message says what was requested, what happened, why, and what to try."""


class CameraConfigurationError(RuntimeError):
    """Camera workers could not supply the requested configurations."""
