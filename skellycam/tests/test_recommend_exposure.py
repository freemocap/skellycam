from types import SimpleNamespace
import asyncio

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.tasks.recommend_exposure import recommend_exposure


class CameraFrames:
    def __init__(self, stale=False):
        self.configs = {key: CameraConfig(camera_id=key, exposure=-7, exposure_mode="AUTO")
                        for key in ("one", "two", "untouched")}
        self.number = 0
        self.stale = stale
        self.applied = []

    async def update_camera_settings(self, requested_configs):
        self.configs = requested_configs
        self.applied.append(requested_configs)
        return self.configs

    def get_latest_frames(self):
        self.number += int(not self.stale)
        return {key: SimpleNamespace(
            frame_metadata=SimpleNamespace(frame_number=[self.number]),
            image=[np.full((2, 2, 3), 127.5 + (config.exposure - optimum) * 30)],
        ) for (key, config), optimum in zip(self.configs.items(), (-7, -6, -5))}


@pytest.mark.asyncio
async def test_recommendation_never_probes_exposure_above_minus_five():
    group = CameraFrames()
    await recommend_exposure(group, {"one"}, settle_frames=1)
    assert all(configs["one"].exposure <= -5 for configs in group.applied)
    with pytest.raises(ValueError, match="at most -5"):
        await recommend_exposure(group, {"one"}, candidates=(-5, -4))


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["python", "rust"])
@pytest.mark.parametrize("mode,requested,expected", [("MANUAL", -4, -5), ("MANUAL", -3, -5),
                                                    ("MANUAL", -7, -7), ("AUTO", -4, -4)])
async def test_camera_requests_limit_manual_exposure_without_changing_saved_data(monkeypatch, backend, mode, requested, expected):
    from skellycam.core.camera_group import camera_backend_manager as selection
    from skellycam.core.camera_group import camera_group_manager as python_backend

    class Manager:
        def __init__(self, **kwargs):
            self.camera_groups = {}

        async def create_or_update_camera_group(self, configs):
            assert configs["one"].exposure == expected
            return SimpleNamespace(configs=configs)

    monkeypatch.setattr(python_backend, "CameraGroupManager", Manager)
    monkeypatch.setattr(selection, "RustCameraGroupManager", Manager)
    manager = selection.CameraBackendManager(global_kill_flag=None, worker_registry=None)
    config = CameraConfig(camera_id="one", exposure_mode=mode, exposure=requested)
    await manager.create_or_update_camera_group({"one": config}, backend=backend)
    assert config.exposure == requested


@pytest.mark.asyncio
async def test_shared_task_selects_per_camera_exposure_and_preserves_other_settings():
    group = CameraFrames()
    values = await recommend_exposure(group, {"one", "two"}, candidates=(-8, -7, -6), settle_frames=2)
    assert values == {"one": -8, "two": -7}
    assert group.configs["untouched"].exposure_mode == "AUTO"
    assert group.configs["one"].exposure_mode == "MANUAL"
    assert len(group.applied) == 4


@pytest.mark.asyncio
async def test_stale_frames_timeout_and_restore_original_settings():
    group = CameraFrames(stale=True)
    with pytest.raises(TimeoutError, match="fresh exposure samples"):
        await recommend_exposure(group, {"one"}, frame_timeout=0.01)
    assert group.configs["one"].exposure_mode == "AUTO"
    assert group.configs["one"].exposure == -7


@pytest.mark.asyncio
async def test_cancellation_restores_original_settings():
    group = CameraFrames(stale=True)
    task = asyncio.create_task(recommend_exposure(group, {"one"}))
    await asyncio.sleep(0.01)
    assert group.configs["one"].exposure_mode == "MANUAL"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert group.configs["one"].exposure_mode == "AUTO"


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["python", "rust"])
async def test_manager_routes_recommendation_through_shared_task(monkeypatch, backend):
    from skellycam.core.camera_group import camera_backend_manager as selection
    from skellycam.core.camera_group import camera_group_manager as python_backend

    class Manager:
        def __init__(self, **kwargs):
            self.camera_groups = {}

        async def create_or_update_camera_group(self, configs):
            assert configs["one"].exposure_mode == "MANUAL"
            return SimpleNamespace(configs=configs)

    calls = []

    async def recommend(group, camera_ids):
        calls.append(camera_ids)

    monkeypatch.setattr(selection.sys, "platform", "win32")
    monkeypatch.setattr(python_backend, "CameraGroupManager", Manager)
    monkeypatch.setattr(selection, "RustCameraGroupManager", Manager)
    monkeypatch.setattr(selection, "recommend_exposure", recommend)
    manager = selection.CameraBackendManager(global_kill_flag=None, worker_registry=None)
    config = CameraConfig(camera_id="one", exposure_mode="RECOMMEND")
    await manager.create_or_update_camera_group({"one": config}, backend=backend)
    assert calls == [{"one"}]
    assert config.exposure_mode == "RECOMMEND"
