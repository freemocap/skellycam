import uuid

from skellycam.core.types.type_overloads import CameraGroupIdString


def create_camera_group_id() -> CameraGroupIdString:
    return str(uuid.uuid4())[:6]  # Shortened UUID for readability
