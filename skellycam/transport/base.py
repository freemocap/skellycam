import abc
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict


class TransportType(str, Enum):
    WEBSOCKET = "websocket"
    UDP = "udp"
    ZEROMQ = "zeromq"
    ARROW = "arrow"


class TransportConfig(BaseModel):
    """Base configuration for transport implementations."""

    model_config = ConfigDict(frozen=True)

    transport_type: TransportType
    enabled: bool = True


class TransportBase(abc.ABC):
    """Abstract base class for transport protocol implementations.

    All transport implementations (WebSocket, UDP, ZeroMQ, Arrow) must inherit
    from this class and implement the abstract methods to provide a unified API
    for sending camera frames and managing connections.
    """

    def __init__(self, config: TransportConfig) -> None:
        self.config = config
        self._frame_callback: Callable[[str, int, bytes, dict[str, Any]], Any] | None = None

    @abc.abstractmethod
    async def start(self) -> None:
        """Initialize and start the transport."""
        ...

    @abc.abstractmethod
    async def stop(self) -> None:
        """Cleanup and stop the transport."""
        ...

    @abc.abstractmethod
    async def send_frame(
        self,
        camera_id: str,
        timestamp_ns: int,
        frame_data: bytes,
        metadata: dict[str, Any],
    ) -> None:
        """Send binary frame data through the transport."""
        ...

    def register_frame_callback(
        self, callback: Callable[[str, int, bytes, dict[str, Any]], Any]
    ) -> None:
        """Register a callback for receiving frames.

        Args:
            callback: Callable to invoke when a frame is received. Should accept
                     camera_id, timestamp_ns, frame_data, and metadata arguments.
        """
        self._frame_callback = callback

    def _invoke_frame_callback(
        self, camera_id: str, timestamp_ns: int, frame_data: bytes, metadata: dict[str, Any]
    ) -> None:
        """Invoke the registered frame callback if one exists.

        This method should be called by subclasses when they receive frames.
        """
        if self._frame_callback is not None:
            self._frame_callback(camera_id, timestamp_ns, frame_data, metadata)
