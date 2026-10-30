"""Opt-in regression for state polling during native camera lifecycle calls."""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.mark.skipif(
    "SKELLYCAM_TEST_NATIVE_CAMERA_INDEX" not in os.environ,
    reason="Requires an explicitly selected, available physical camera",
)
def test_polling_during_native_group_creation_and_closure():
    import _skellycam_rust

    manager = _skellycam_rust.CameraGroupManager()
    configs = {"polling-test": {
        "camera_index": int(os.environ["SKELLYCAM_TEST_NATIVE_CAMERA_INDEX"]),
        "width": 640, "height": 480, "framerate": 30.0,
    }}

    def await_with_polling(future):
        deadline = time.monotonic() + 30
        polls = 0
        while not future.done():
            assert time.monotonic() < deadline, "Native lifecycle call timed out"
            manager.to_state_dict()
            manager.get_latest_frame_payloads()
            manager.list_groups()
            polls += 1
            time.sleep(0.001)
        return future.result(), polls

    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            group_id, creation_polls = await_with_polling(
                executor.submit(manager.create_or_update_group, configs)
            )
            assert creation_polls > 0
            deadline = time.monotonic() + 10
            while not manager.get_latest_frame_payloads():
                assert time.monotonic() < deadline, "Camera did not deliver a frame"
                time.sleep(0.01)
            _, closure_polls = await_with_polling(
                executor.submit(manager.close_group, group_id)
            )
            assert closure_polls > 0
            assert manager.list_groups() == []
        finally:
            # Wait for outstanding work before final cleanup on a test failure.
            executor.shutdown(wait=True)
            manager.close_all_groups()
