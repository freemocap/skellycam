import logging
import multiprocessing
import time
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO, CameraGroupSharedMemoryOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.timestamps.framerate_tracker import FrameRateTracker
from skellycam.core.videos.video_recorder_manager import VideoRecorderManager
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameWrangler:
    def __init__(self,
                 camera_group_dto: CameraGroupDTO,
                 shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                 new_configs_queue: multiprocessing.Queue):
        self.camera_group_dto = camera_group_dto
        self.shmorc_dto = shmorc_dto
        self.new_configs_queue = new_configs_queue
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_group_dto,
                                                      shmorc_dto,
                                                      new_configs_queue,
                                                      )
                                                )

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self._process.start()

    def join(self):
        self._process.join()

    @staticmethod
    def _run_process(camera_group_dto: CameraGroupDTO,
                     shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                     new_configs_queue: multiprocessing.Queue):
        logger.debug(f"FrameWrangler process started!")
        camera_group_shm = CameraGroupSharedMemoryOrchestrator.recreate(camera_group_dto=camera_group_dto,
                                                                       shmorc_dto=shmorc_dto,
                                                                       read_only=False).shm
        framerate_tracker = FrameRateTracker()
        mf_payload: Optional[MultiFramePayload] = None
        camera_configs = camera_group_dto.camera_configs
        video_recorder_manager: Optional[VideoRecorderManager] = None
        try:
            while not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                wait_1ms()

                if new_configs_queue.qsize() > 0:
                    if camera_group_dto.ipc_flags.record_frames_flag.value:
                        raise RuntimeError("Cannot change camera configs while recording! Ignoring new configs until recording is over...")
                    camera_configs = new_configs_queue.get()

                if camera_group_shm.new_data_available:
                    mf_payload: MultiFramePayload = camera_group_shm.get_next_multi_frame_payload(
                        previous_payload=mf_payload,
                        camera_configs=camera_configs,
                    )
                    framerate_tracker.update(time.perf_counter_ns())
                elif video_recorder_manager:
                    video_recorder_manager.save_one_frame() #returns None if nothing to save

                if camera_group_dto.ipc_flags.record_frames_flag.value:
                    if not video_recorder_manager:
                        logger.info("Recording started, creating video recorder...")
                        video_recorder_manager = VideoRecorderManager(
                            camera_group_dto=camera_group_dto,
                            camera_configs=camera_configs,
                        )
                        camera_group_dto.ipc_queue.put(video_recorder_manager.recording_info)
                    video_recorder_manager.add_multi_frame(mf_payload) if mf_payload else None
                else:
                    if video_recorder_manager:
                        logger.info("Recording complete, closing video recorder...")
                        video_recorder_manager.finish_and_close()
                        video_recorder_manager = None
        except Exception as e:
            logger.exception(f"FrameWrangler process exited with exception: {e}")
            raise
        finally:
            if video_recorder_manager:
                video_recorder_manager.finish_and_close()
            camera_group_shm.close()
            camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            logger.info("FrameWrangler process exiting...")