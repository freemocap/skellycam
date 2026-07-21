import enum


class WebsocketMessageType(str, enum.Enum):
    """All JSON message types sent over the websocket.

    Inherits from str so it serializes to its string value in JSON automatically.
    The frontend sees e.g. "framerate_update" — no change to the wire format.
    """
    FRAMERATE_UPDATE = "framerate_update"
    APP_STATE = "app_state"
    PERFORMANCE_DATA = "performance_data"
    LOG_RECORD = "log_record"
