"""
Pydantic models for WebSocket messages (data plane only).

Client → Server:
  WebsocketFrameAcknowledgement  — backpressure control

Server → Client:
  WebsocketFramerateUpdate       — framerate stats
  WebsocketAppState              — periodic app state snapshot
"""
from typing import Literal, Any

from pydantic import BaseModel, Field, ConfigDict


class WebsocketFrameAcknowledgement(BaseModel):
    """Frame acknowledgment from the client (backpressure control)."""
    type: Literal["frame_acknowledgement"] = "frame_acknowledgement"
    frame_number: int = Field(alias="frameNumber")
    display_image_sizes: dict[str, object] | None = Field(None, alias="displayImageSizes")

    model_config = ConfigDict(populate_by_name=True)


class WebsocketFramerateUpdate(BaseModel):
    type: Literal["framerate_update"] = "framerate_update"
    camera_group_id: str
    backend_framerate: dict[str, Any]
    frontend_framerate: dict[str, Any]


class WebsocketAppState(BaseModel):
    type: Literal["app_state"] = "app_state"
    state: dict[str, Any]
