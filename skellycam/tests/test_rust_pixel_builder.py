"""Rust tracker frames land in SkellyCam shared memory at SkellyCam frame numbers, in the OpenCV layout.

Readers (Core's realtime nodes, SkellyCam's own) fetch frame N at ring index N. The pixel builder writes only the
newest frameset, so frame numbers may skip; each frame still sits at its own number.
"""
import asyncio
import time
from unittest.mock import Mock

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping

CONFIGS = {camera_id: CameraConfig(camera_id=camera_id, camera_index=index, rotation=0,
                                   resolution={"width": 8, "height": 6})
           for index, camera_id in enumerate(("A", "B"))}


def test_frames_written_out_of_sequence_sit_at_their_own_numbers():
    shm = CameraGroupSharedMemory.create(CONFIGS, TimebaseMapping())
    try:
        for number in (3, 7):
            for ring in shm.camera_shms.values():
                slot = ring.frame_slot(number)
                slot["frame_metadata"]["frame_number"] = number
                slot["image"][0] = number
                ring.commit_frame(number)
        assert shm.latest_multiframe_number == 7
        for number in (3, 7):
            frame = shm.camera_shms["A"].get_data_by_index(index=number, rec_array=None)
            assert int(frame.frame_metadata.frame_number[0]) == number and np.all(frame.image[0] == number)
        with pytest.raises(ValueError, match="not newer"):
            shm.camera_shms["A"].commit_frame(7)
    finally:
        shm.unlink_and_close()


class FakeFrameset:
    """Stands in for the native Frameset: decode_into fills each destination with the frame number."""

    def __init__(self, frame_number: int):
        self.frame_number = frame_number

    def cameras(self):
        return {camera_id: {"camera_index": config.camera_index, "width": 8, "height": 6, "rotation": 0,
                            "loop_start_ns": 1000 * self.frame_number, "frame_available_ns": 1000 * self.frame_number + 7}
                for camera_id, config in CONFIGS.items()}

    def decode_into(self, targets):
        assert set(targets) == set(CONFIGS)
        for target in targets.values():
            assert target.shape == (6, 8, 3) and target.flags.writeable
            target[:] = self.frame_number


def test_first_decode_failure_releases_memory_and_allows_retry(monkeypatch):
    frameset = FakeFrameset(41)
    native = Mock()
    native.newest_frameset.side_effect = lambda group_id, cursor: frameset if cursor < 0 else None
    group = RustCameraGroup("g", CONFIGS, native)
    try:
        with monkeypatch.context() as patch:
            decode = Mock(side_effect=ValueError("bad first JPEG"))
            patch.setattr(frameset, "decode_into", decode)
            with pytest.raises(ValueError, match="bad first JPEG"):
                group.shm
        assert group._shm is None and group._pixel_thread is None
        assert group.transport_error == "ValueError: bad first JPEG"
        assert group.shm.latest_multiframe_number == 41
        assert group.transport_error is None
    finally:
        asyncio.run(group.close())


def test_pixel_builder_writes_newest_framesets_at_skellycam_frame_numbers():
    pending = [FakeFrameset(45)]
    native = Mock()
    native.newest_frameset.side_effect = lambda group_id, if_newer_than: (
        FakeFrameset(41) if if_newer_than == -1 else (pending.pop() if pending and if_newer_than == 41 else None))
    group = RustCameraGroup("g", CONFIGS, native)
    shm = group.shm
    deadline = time.monotonic() + 5
    while shm.latest_multiframe_number != 45 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert shm.latest_multiframe_number == 45
    for number in (41, 45):
        for camera_id, ring in shm.camera_shms.items():  # as Core's camera nodes read: index = frame number
            frame = ring.get_data_by_index(index=number, rec_array=None)
            metadata = frame.frame_metadata
            assert int(metadata.frame_number[0]) == number and np.all(frame.image[0] == number)
            assert metadata.camera_info.camera_id[0] == camera_id and int(metadata.camera_info.rotation[0]) == 0
            assert (int(metadata.timestamps.pre_frame_grab_ns[0]),
                    int(metadata.timestamps.post_frame_grab_ns[0])) == (1000 * number, 1000 * number + 7)
            assert int(metadata.timestamps.pre_copy_to_camera_shm_ns[0]) == 0
    asyncio.run(group.close())  # stops the builder, closes the native group, releases the memory
    assert group.transport_error is None and not group._pixel_thread.is_alive()
    native.close_group.assert_called_once_with("g")
