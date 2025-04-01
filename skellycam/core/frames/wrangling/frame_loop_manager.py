import logging
import multiprocessing
import threading
import time
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestrator, CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.framerate_tracker import FramerateTracker
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameLoopManager:
    def __init__(
            self,
            camera_group_dto: CameraGroupDTO,
            shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
            new_configs_queue: multiprocessing.Queue,
    ):
        self._worker = multiprocessing.Process(target=self._run_worker,
                                               name=self.__class__.__name__,
                                               daemon=True,
                                               kwargs=dict(camera_group_dto=camera_group_dto,
                                                           shmorc_dto=shmorc_dto,
                                                           new_configs_queue=new_configs_queue
                                                           )
                                               )

    def start(self):
        logger.trace(f"Starting frame listener worker...")
        self._worker.start()

    @staticmethod
    def _run_worker(camera_group_dto: CameraGroupDTO,
                    shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                    new_configs_queue: multiprocessing.Queue,
                    ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=camera_group_dto.ipc.ws_logs_queue)
        logger.trace(f"Starting frame loop...")
        shmorchestrator = CameraGroupSharedMemoryOrchestrator.recreate(camera_group_dto=camera_group_dto,
                                                                       shmorc_dto=shmorc_dto,
                                                                       read_only=False)
        orchestrator = shmorchestrator.orchestrator
        camera_group_shm = shmorchestrator.camera_group_shm
        multi_frame_escape_shm = shmorchestrator.multiframe_escape_ring_shm

        frame_loop_trigger_thread = threading.Thread(target=frame_read_trigger_loop,
                                                     kwargs=dict(orchestrator=orchestrator,
                                                                 camera_group_dto=camera_group_dto),
                                                     daemon=True)
        frame_loop_trigger_thread.start()

        backend_framerate_tracker = FramerateTracker.create(framerate_source="backend")
        mf_payload: MultiFramePayload|None = None
        camera_configs = camera_group_dto.camera_configs
        try:
            while camera_group_dto.should_continue:
                if not new_configs_queue.empty():
                    camera_configs = new_configs_queue.get()

                if orchestrator.should_pull_multi_frame_from_shm.value and orchestrator.new_multi_frame_available:

                    mf_payload: MultiFramePayload = camera_group_shm.get_multi_frame_payload(
                        previous_payload=mf_payload,
                        camera_configs=camera_configs,
                    )
                    logger.loop(
                        f"FrameListener - copied multi-frame payload# {mf_payload.multi_frame_number} from shared memory")
                    orchestrator.signal_multi_frame_pulled_from_shm()
                    backend_framerate_tracker.update(time.perf_counter_ns())
                    multi_frame_escape_shm.put_multi_frame_payload(mf_payload)
                    if mf_payload.multi_frame_number % 10 == 0:
                        # update every 10  multi-frames to avoid overloading the queue
                        camera_group_dto.ipc.ws_ipc_relay_queue.put(backend_framerate_tracker.current_framerate)
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
            logger.trace(f"FrameEscaperWorker shutting down...")
            if camera_group_dto.should_continue:
                raise RuntimeError(
                    "FrameListenerProcess was closed before the camera group or global kill flag(s) were set.")
            if not camera_group_dto.ipc.kill_camera_group_flag.value:
                logger.trace(f"FrameListenerProcess shutting down - setting kill_camera_group_flag to True")
                camera_group_dto.ipc.kill_camera_group_flag.value = True
            camera_group_shm.close()
            multi_frame_escape_shm.close()

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    def join(self):
        self._worker.join()

def frame_read_trigger_loop(orchestrator: CameraGroupOrchestrator, camera_group_dto: CameraGroupDTO):
    orchestrator.await_cameras_ready()
    current_loop = orchestrator.loop_count.value
    logger.debug("Triggering initial multi-frame read...")
    orchestrator.trigger_multi_frame_read()
    logger.debug("Multi-frame read loop started...")
    while camera_group_dto.should_continue:
        if current_loop != orchestrator.loop_count.value:
            current_loop = orchestrator.loop_count.value
            orchestrator.trigger_multi_frame_read()
        else:
            wait_1ms()