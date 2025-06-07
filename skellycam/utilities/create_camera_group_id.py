import uuid

from skellycam.core.types import CameraGroupIdString


def create_camera_group_id() -> CameraGroupIdString:
    return str(uuid.uuid4())[:6]  # Shortened UUID for readability
