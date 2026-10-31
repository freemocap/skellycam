"""One exposure-selection task for any streaming camera-group implementation."""
import asyncio
from typing import Protocol, runtime_checkable

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs, MAX_MANUAL_EXPOSURE


@runtime_checkable
class ExposureCameraGroup(Protocol):
    configs: CameraConfigs

    def get_latest_frames(self) -> dict[str, np.recarray] | None: ...

    async def update_camera_settings(self, requested_configs: CameraConfigs) -> CameraConfigs: ...


async def recommend_exposure(
    group: ExposureCameraGroup,
    camera_ids: set[str],
    *,
    candidates: tuple[int, ...] = tuple(range(-12, MAX_MANUAL_EXPOSURE + 1)),
    settle_frames: int = 10,
    frame_timeout: float = 5.0,
    offset: int = -1,
) -> dict[str, int]:
    """Choose manual exposure nearest mean brightness 127.5, then apply offset.

    Frame numbers, not polling iterations, count toward settling. All selected
    cameras are sampled together; other cameras retain their settings. Restore
    the starting configuration if capture, configuration, or cancellation fails.
    The caller serializes this task against other group configuration changes.
    """
    if not camera_ids:
        return {}
    if not candidates or settle_frames < 1 or not camera_ids <= group.configs.keys():
        raise ValueError("Exposure task requires candidates, settling frames, and known camera IDs")
    if any(candidate > MAX_MANUAL_EXPOSURE for candidate in candidates):
        raise ValueError(f"Manual exposure candidates must be at most {MAX_MANUAL_EXPOSURE}")
    original = {key: value.model_copy(deep=True) for key, value in group.configs.items()}
    best: dict[str, tuple[float, int]] = {}

    async def apply(values):
        configs = {key: value.model_copy(deep=True) for key, value in original.items()}
        for key, exposure in values.items():
            configs[key].exposure_mode = "MANUAL"
            configs[key].exposure = exposure
        await group.update_camera_settings(configs)

    try:
        for exposure in candidates:
            await apply(dict.fromkeys(camera_ids, exposure))
            initial = group.get_latest_frames() or {}
            seen = {key: int(frame.frame_metadata.frame_number[0]) for key, frame in initial.items()}
            remaining = dict.fromkeys(camera_ids, settle_frames)
            deadline = asyncio.get_running_loop().time() + frame_timeout
            while remaining:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError(f"No fresh exposure samples from cameras {sorted(remaining)}")
                for key, frame in (group.get_latest_frames() or {}).items():
                    number = int(frame.frame_metadata.frame_number[0])
                    if key not in remaining or seen.get(key) == number:
                        continue
                    seen[key] = number
                    remaining[key] -= 1
                    if remaining[key] == 0:
                        difference = abs(float(np.mean(frame.image[0])) - 127.5)
                        if key not in best or difference < best[key][0]:
                            best[key] = (difference, exposure)
                        del remaining[key]
                await asyncio.sleep(0.005)
        selected = {key: max(min(candidates), min(max(candidates), value + offset))
                    for key, (_, value) in best.items()}
        await apply(selected)
        return selected
    except BaseException:
        await group.update_camera_settings(original)
        raise
