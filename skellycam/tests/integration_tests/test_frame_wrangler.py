import multiprocessing

import numpy as np

from skellycam.core.frames.frame_payload import FramePayload


def test_frame_wrangler(camera_shared_memory_fixture: "CameraSharedMemoryManager",
                        multi_camera_triggers_fixture: "MultiCameraTriggers"
                        ):
    from skellycam.core.frames.frame_wrangler import FrameWrangler

    og_shm_manager = camera_shared_memory_fixture[0]
    child_shm_manager = camera_shared_memory_fixture[1]
    child_shm_manager.close()

    camera_configs = og_shm_manager.camera_configs

    exit_event = multiprocessing.Event()

    frame_wrangler = FrameWrangler(exit_event=exit_event)
    frame_wrangler.set_camera_info(camera_configs=camera_configs,
                                   shm_lock=og_shm_manager._lock,
                                   shared_memory_names=og_shm_manager.shared_memory_names,
                                   multicam_triggers=multi_camera_triggers_fixture
                                   )
    frame_wrangler.start_frame_listener()
    number_of_frames_to_test = 4
    for frame_number in range(number_of_frames_to_test):
        for camera_id, config in camera_configs.items():
            cam_shm = og_shm_manager.get_camera_shared_memory(camera_id)
            cam_triggers = multi_camera_triggers_fixture.single_camera_triggers[camera_id]
            image = np.random.randint(0, 256, size=config.image_shape, dtype=np.uint8)
            unhydrated_frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                                    image=image)
            assert not unhydrated_frame.hydrated
            assert not multi_camera_triggers_fixture.new_frames_available
            assert not cam_triggers.new_frame_available
            cam_shm.put_new_frame(image=image,
                                  frame=unhydrated_frame)
            cam_triggers.set_frame_retrieved()
            assert cam_triggers.new_frame_available

        assert multi_camera_triggers_fixture.new_frames_available
        multi_camera_triggers_fixture.set_frames_copied()
        multi_camera_triggers_fixture._await_frames_copied()
        assert not multi_camera_triggers_fixture.new_frames_available

    frame_wrangler.close()
