"""Live readers retain independent image snapshots between requests."""

from unittest.mock import Mock

import numpy as np

from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer


def test_next_reader_cannot_overwrite_a_retained_multiframe() -> None:
    dtype = np.dtype([
        ("frame_metadata", [("frame_number", "i8")]),
        ("image", "u1", (2, 2, 3)),
    ])

    def read(*, index: int, rec_array: np.recarray | None) -> np.recarray:
        result = np.zeros(1, dtype=dtype).view(np.recarray) if rec_array is None else rec_array
        result.frame_metadata.frame_number[0] = index
        result.image[:] = index
        return result

    cameras: dict[str, CameraSharedMemoryRingBuffer] = {}
    for camera_id in ("left", "right"):
        camera = Mock(spec=CameraSharedMemoryRingBuffer)
        camera.latest_frame_number = 1
        camera.get_data_by_index.side_effect = read
        cameras[camera_id] = camera
    group = CameraGroupSharedMemory(camera_shms=cameras, camera_configs={}, read_only=True)
    retained = group.get_latest_multiframe()
    assert retained is not None
    for camera in cameras.values():
        camera.latest_frame_number = 2
    subsequent = group.get_latest_multiframe()
    assert subsequent is not None
    for camera_id in cameras:
        assert retained[camera_id].frame_metadata.frame_number[0] == 1
        assert np.all(retained[camera_id].image == 1)
        assert subsequent[camera_id].frame_metadata.frame_number[0] == 2
        assert not np.shares_memory(retained[camera_id], subsequent[camera_id])
