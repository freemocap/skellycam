import logging
import multiprocessing
import time
from typing import Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.frame_saver import FrameSaver
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.system.default_paths import create_recording_folder
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            group_shm_names: GroupSharedMemoryNames,
            group_orchestrator: CameraGroupOrchestrator,
            multiframe_queue: multiprocessing.Queue,
            exit_event: multiprocessing.Event,
    ):
        super().__init__()
        self._payloads_received: multiprocessing.Value = multiprocessing.Value("i", 0)

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_configs,
                                                      group_shm_names,
                                                      group_orchestrator,
                                                      self._payloads_received,
                                                      multiframe_queue,
                                                      exit_event,
                                                      )
                                                )

    @property
    def payloads_received(self) -> int:
        return self._payloads_received.value

    def start_process(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     group_shm_names: GroupSharedMemoryNames,
                     group_orchestrator: CameraGroupOrchestrator,
                     payloads_received: multiprocessing.Value,
                     multiframe_queue: multiprocessing.Queue,
                     exit_event: multiprocessing.Event):
        logger.trace(f"Frame listener process started!")
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        try:

            group_orchestrator.await_for_cameras_ready()
            mf_payload: Optional[MultiFramePayload] = None
            logger.loop(f"Starting FrameListener loop...")
            # Frame listener loop
            while not exit_event.is_set():
                if group_orchestrator.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")
                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload)
                    # Reset the flag to allow new frame loop to begin BEFORE we put the payload in the queue
                    group_orchestrator.set_frames_copied()
                    mf_payload.lifespan_timestamps_ns.append({"before_put_in_mf_queue": time.perf_counter_ns()})
                    multiframe_queue.put(mf_payload)
                    payloads_received.value += 1
                else:
                    wait_1ms()
        except Exception as e:
            logger.error(f"Frame listener process error: {e}")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            camera_group_shm.close()  # close but don't unlink - parent process will unlink
            try:
                multiframe_queue.put(None)
            except BrokenPipeError:
                pass

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()


class FrameExporterProcess:
    def __init__(self,
                 multiframe_queue: multiprocessing.Queue,
                 frontend_queue: multiprocessing.Queue,
                 camera_configs: CameraConfigs,
                 exit_event: multiprocessing.Event, ):

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(multiframe_queue,
                                                      frontend_queue,
                                                      camera_configs,
                                                      exit_event))

    def start_process(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()

    @staticmethod
    def _run_process(multiframe_queue: multiprocessing.Queue,
                     frontend_queue: multiprocessing.Queue,
                     camera_configs: CameraConfigs,
                     exit_event: multiprocessing.Event,
                     record_frames: multiprocessing.Event = multiprocessing.Event(),
                     ):
        logger.trace(f"Frame exporter process started!")
        frame_saver: Optional[FrameSaver] = None

        try:
            while not exit_event.is_set():
                if not multiframe_queue.empty():
                    mf_payload: MultiFramePayload = multiframe_queue.get()
                    mf_payload.lifespan_timestamps_ns.append({"pulled_from_mf_queue": time.perf_counter_ns()})
                    if not mf_payload:
                        logger.trace(f"Received empty payload - exiting")
                        break
                    logger.loop(f"FrameExporter - Received multi-frame payload: {mf_payload}")
                    if record_frames.is_set():
                        if not frame_saver:
                            frame_saver = FrameSaver.create(mf_payload=mf_payload,
                                                            camera_configs=camera_configs,
                                                            recording_folder=create_recording_folder(string_tag=None))
                        frame_saver.add_multi_frame(mf_payload)

                    mf_payload.lifespan_timestamps_ns.append({"put_in_frontend_queue": time.perf_counter_ns()})
                    frontend_queue.put(FrontendFramePayload.from_multi_frame_payload(mf_payload))
                else:
                    wait_1ms()
        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
        finally:
            try:
                multiframe_queue.put(None)
            except Exception as e:
                pass
            try:
                frontend_queue.put(None)
            except Exception as e:
                pass
            logger.trace(f"Stopped listening for multi-frames")
            if frame_saver:
                frame_saver.close()
            exit_event.set()


class FrameWrangler:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_shm_names: GroupSharedMemoryNames,
                 group_orchestrator: CameraGroupOrchestrator,
                 frontend_payload_queue: multiprocessing.Queue,
                 exit_event: multiprocessing.Event):
        super().__init__()
        self._exit_event = exit_event

        camera_configs: CameraConfigs = camera_configs
        group_orchestrator: CameraGroupOrchestrator = group_orchestrator

        self._multiframe_queue = multiprocessing.Queue()
        self._listener_process = FrameListenerProcess(
            camera_configs=camera_configs,
            group_orchestrator=group_orchestrator,
            group_shm_names=group_shm_names,
            multiframe_queue=self._multiframe_queue,
            exit_event=self._exit_event,
        )
        self._exporter_process = FrameExporterProcess(
            multiframe_queue=self._multiframe_queue,
            frontend_queue=frontend_payload_queue,
            camera_configs=camera_configs,
            exit_event=self._exit_event,
        )

    @property
    def payloads_received(self) -> Optional[int]:
        if self._listener_process is None:
            return None
        return self._listener_process.payloads_received

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self._listener_process.start_process()
        self._exporter_process.start_process()

    def is_alive(self) -> bool:
        if self._listener_process is None or self._exporter_process is None:
            return False
        return self._listener_process.is_alive() and self._exporter_process.is_alive()

    def join(self):
        self._listener_process.join()
        self._exporter_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._exit_event.set()
        self._multiframe_queue.put(None)
        if self.is_alive():
            self.join()
        self._multiframe_queue.close()
        logger.debug(f"Frame wrangler closed")
