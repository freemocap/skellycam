class CameraStateConflict(ValueError):
    """A requested camera operation conflicts with an active recording."""


class CameraConnectionCancelled(RuntimeError):
    """The group stopped before this camera finished connecting."""


class CameraConfigurationError(RuntimeError):
    """Camera workers could not supply the requested configurations."""
