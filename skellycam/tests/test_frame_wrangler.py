from typing import Tuple

import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


@pytest.mark.asyncio
async def test_frame_wrangler(shared_memory_fixture: Tuple[CameraSharedMemoryManager, CameraSharedMemoryManager],
                        camera_configs_fixture:CameraConfigs,):
    og_shm_manager = shared_memory_fixture[0]
    recreated_shm_manager = shared_memory_fixture[1]

    frame_wrangler = FrameWrangler()

    frame_wrangler.set_shared_memory_manager(shared_memory_manager=og_shm_manager)

    frame_wrangler.set_camera_configs(camera_configs=camera_configs_fixture, shared_memory_manager=og_shm_manager)

    frame_wrangler.start_frame_listener()

    await frame_wrangler.close()