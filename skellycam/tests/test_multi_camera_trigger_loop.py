# import multiprocessing
# import time
#
# from skellycam.core.cameras.trigger_camera.multi_camera_trigger_loop import multi_camera_trigger_loop
# from skellycam.tests.mocks import create_cv2_video_capture_mock
#
#
# def test_multi_camera_trigger_loop(camera_configs_fixture,
#                                    camera_shared_memory_fixture,
#                                    ):
#     shm_manager, recreated_shm_manager = camera_shared_memory_fixture
#     shm_names = shm_manager.shared_memory_names
#     lock = shm_manager.lock
#     exit_event = multiprocessing.Event()
#     multi_camera_trigger_loop(camera_configs=camera_configs_fixture,
#                               shared_memory_names=shm_names,
#                               lock=lock,
#                               exit_event=exit_event
#                               )
#     time.sleep(3)
#     exit_event.set()
#     time.sleep(3)
#     assert True
#
#
# def _ensure_mock():
#     # Quick check to ensure the function is mocked
#     from skellycam.core.cameras.opencv.create_cv2_video_capture import create_cv2_capture
#     return create_cv2_capture == create_cv2_video_capture_mock
