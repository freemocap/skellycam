"""
Camera group state machine with validated transitions.
Pure domain logic — no WebSocket types.
"""
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class CameraGroupStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    STREAMING = "streaming"
    RECORDING = "recording"


VALID_TRANSITIONS: dict[CameraGroupStatus, set[CameraGroupStatus]] = {
    CameraGroupStatus.DISCONNECTED: {CameraGroupStatus.CONNECTED},
    CameraGroupStatus.CONNECTED: {CameraGroupStatus.STREAMING, CameraGroupStatus.DISCONNECTED},
    CameraGroupStatus.STREAMING: {CameraGroupStatus.RECORDING, CameraGroupStatus.DISCONNECTED},
    CameraGroupStatus.RECORDING: {CameraGroupStatus.STREAMING, CameraGroupStatus.DISCONNECTED},
}


class InvalidTransitionError(Exception):
    pass


class CameraGroupStateMachine:
    def __init__(self) -> None:
        self._phase = CameraGroupStatus.DISCONNECTED

    @property
    def phase(self) -> CameraGroupStatus:
        return self._phase

    def transition(self, to: CameraGroupStatus) -> None:
        """Transition to a new phase. Raises InvalidTransitionError if the transition is not allowed."""
        allowed = VALID_TRANSITIONS.get(self._phase, set())
        if to not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self._phase.value} to {to.value}. "
                f"Allowed: {[p.value for p in allowed]}"
            )
        logger.info(f"Camera group state: {self._phase.value} → {to.value}")
        self._phase = to

    def force_disconnect(self) -> None:
        """Force transition to DISCONNECTED from any state."""
        if self._phase != CameraGroupStatus.DISCONNECTED:
            logger.info(f"Camera group state: {self._phase.value} → disconnected (forced)")
            self._phase = CameraGroupStatus.DISCONNECTED
