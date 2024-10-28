import logging
import multiprocessing
import time
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestrator, CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.image_annotation import ImageAnnotator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.timestamps.framerate_tracker import FrameRateTracker
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            camera_group_dto: CameraGroupDTO,
            shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
            new_configs_queue: multiprocessing.Queue):
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_group_dto,
                                                      shmorc_dto,
                                                      new_configs_queue,
                                                      )
                                                )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(camera_group_dto: CameraGroupDTO,
                     shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                     new_configs_queue: multiprocessing.Queue,
                     ):
        logger.trace(f"Starting FrameListener loop...")
        shmorchestrator = CameraGroupSharedMemoryOrchestrator.recreate(camera_group_dto=camera_group_dto,
                                                                       shmorc_dto=shmorc_dto,
                                                                       read_only=False)
        orchestrator = shmorchestrator.orchestrator
        frame_loop_shm = shmorchestrator.frame_loop_shm
        multi_frame_escape_shm = shmorchestrator.multi_frame_escape_ring_shm

        framerate_tracker = FrameRateTracker()
        mf_payload: Optional[MultiFramePayload] = None
        camera_configs = camera_group_dto.camera_configs
        try:

            while not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                if new_configs_queue.qsize() > 0:
                    camera_configs = new_configs_queue.get()

                if orchestrator.should_pull_multi_frame_from_shm.value:

                    tik1 = time.perf_counter_ns()
                    mf_payload: MultiFramePayload = frame_loop_shm.get_multi_frame_payload(
                        previous_payload=mf_payload,
                        camera_configs=camera_configs,
                    )
                    tok1 = time.perf_counter_ns()
                    logger.loop(
                        f"FrameListener - copied multi-frame payload# {mf_payload.multi_frame_number} from shared memory")
                    orchestrator.signal_multi_frame_pulled_from_shm()
                    framerate_tracker.update(time.perf_counter_ns())
                    # for camera_id, frame in mf_payload.frames.items():
                    #     frame.image = image_annotator.annotate_image(image=frame.image,
                    #                                                  frame_number=frame.frame_number,
                    #                                                  multi_frame_number=mf_payload.multi_frame_number,
                    #                                                  framerate_tracker = framerate_tracker,
                    #                                                  camera_id=camera_id)
                    tik2 = time.perf_counter_ns()
                    multi_frame_escape_shm.put_multi_frame_payload(mf_payload)
                    tok2 = time.perf_counter_ns()
                    print(f"Time to pull mf from shm: {(tok1 - tik1) / 1e6} ms, time to put mf into shm: {(tok2 - tik2) / 1e6} ms - recent fps: {framerate_tracker.recent_frames_per_second}")
                else:
                    wait_1ms()

        except Exception as e:
            logger.exception(f"Frame listener process error: {e.__class__} - {e}")
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame exporter process error: {e} - Broken pipe error, problem in FrameRouterProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            logger.info(f"Frame exporter process received KeyboardInterrupt, shutting down gracefully...")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                logger.warning(
                    "FrameListenerProcess was closed before the camera group or global kill flag(s) were set.")
                camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            frame_loop_shm.close()
            multi_frame_escape_shm.close()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()
