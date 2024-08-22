import logging
import multiprocessing
import pickle
import time
from typing import Optional, Union

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.multi_frame_saver import MultiFrameSaver
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.system.default_paths import create_recording_folder
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)

STOP_RECORDING_SIGNAL = "STOP_RECORDING"


class FrameListenerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            group_shm_names: GroupSharedMemoryNames,
            group_orchestrator: CameraGroupOrchestrator,
            video_recorder_queue: multiprocessing.Queue,
            frontend_pipe: multiprocessing.Pipe,
            start_recording_event: multiprocessing.Event,
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
                                                      video_recorder_queue,
                                                      frontend_pipe,
                                                      start_recording_event,
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
                     video_recorder_queue: multiprocessing.Queue,
                     frontend_pipe: multiprocessing.Pipe,
                     start_recording_event: multiprocessing.Event,
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
            is_recording = False
            while not exit_event.is_set():
                if group_orchestrator.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")
                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload)
                    # NOTE - Reset the flag to allow new frame loop to begin BEFORE we put the payload in the queue
                    group_orchestrator.set_frames_copied()

                    if start_recording_event.is_set():
                        logger.info(
                            f"FrameListener - `start_recording_event` set: {start_recording_event.is_set()} - `is_recording`: {is_recording}")
                        is_recording = True
                        mf_payload.lifespan_timestamps_ns.append(
                            {"before_put_in_video_recording_queue": time.perf_counter_ns()})
                        video_recorder_queue.put(mf_payload)
                    elif not start_recording_event.is_set() and is_recording:
                        is_recording = False
                        logger.debug(f"FrameListener - Sending STOP signal to video recorder")
                        video_recorder_queue.put(STOP_RECORDING_SIGNAL)
                    # Pickle and send_bytes, to avoid paying the pickle cost twice when relaying through websocket
                    frontend_bytes = pickle.dumps(FrontendFramePayload.from_multi_frame_payload(mf_payload))
                    frontend_pipe.send_bytes(frontend_bytes)
                    payloads_received.value += 1
            else:
                wait_1ms()
        except Exception as e:
            logger.error(f"Frame listener process error: {e}")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            camera_group_shm.close()  # close but don't unlink - parent process will unlink
            exit_event.set()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()


class VideoRecorderProcess:
    def __init__(self,
                 video_recorder_queue: multiprocessing.Queue,
                 frontend_pipe: multiprocessing.Pipe,
                 camera_configs: CameraConfigs,
                 exit_event: multiprocessing.Event, ):

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(video_recorder_queue,
                                                      frontend_pipe,
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
    def _run_process(video_recorder_queue: multiprocessing.Queue,
                     frontend_pipe: multiprocessing.Pipe,
                     camera_configs: CameraConfigs,
                     exit_event: multiprocessing.Event,
                     ):
        logger.trace(f"Frame exporter process started!")
        multi_frame_saver: Optional[MultiFrameSaver] = None

        try:
            while not exit_event.is_set():
                if not video_recorder_queue.empty():
                    mf_payload: Union[MultiFramePayload, str] = video_recorder_queue.get()
                    if isinstance(mf_payload, str) and mf_payload == STOP_RECORDING_SIGNAL:
                        logger.trace(f"Received STOP signal - closing video recorder")
                        if multi_frame_saver:
                            logger.debug(
                                f"FrameExporter - Closing FrameSaver for recording {multi_frame_saver.recording_name}")
                            multi_frame_saver.close()
                            multi_frame_saver = None
                    elif isinstance(mf_payload, MultiFramePayload):
                        logger.loop(f"FrameExporter - Received multi-frame payload: {mf_payload}")

                        if not multi_frame_saver:
                            multi_frame_saver = MultiFrameSaver.create(mf_payload=mf_payload,
                                                                       camera_configs=camera_configs,
                                                                       recording_folder=create_recording_folder(
                                                                           string_tag=None))
                            logger.success(
                                f"FrameExporter - Created FrameSaver for recording {multi_frame_saver.recording_name}")
                            # send  as bytes so it can use same ws/ relay as the frontend_payload's
                            frontend_pipe.send_bytes(pickle.dumps(multi_frame_saver.recording_info))
                        mf_payload.lifespan_timestamps_ns.append({"pulled_from_mf_queue": time.perf_counter_ns()})

                        multi_frame_saver.add_multi_frame(mf_payload)

                    mf_payload.lifespan_timestamps_ns.append({"put_in_frontend_pipe": time.perf_counter_ns()})
                else:
                    wait_1ms()
        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
            logger.traceback(e)
            raise e
        finally:
            try:
                video_recorder_queue.put(None)
            except Exception as e:
                pass
            try:
                frontend_pipe.send_bytes(None)
            except Exception as e:
                pass
            logger.trace(f"Stopped listening for multi-frames")
            if multi_frame_saver:
                multi_frame_saver.close()
            exit_event.set()


class FrameWrangler:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_shm_names: GroupSharedMemoryNames,
                 group_orchestrator: CameraGroupOrchestrator,
                 frontend_pipe: multiprocessing.Pipe,
                 start_recording_event: multiprocessing.Event,
                 exit_event: multiprocessing.Event):
        super().__init__()
        self._exit_event = exit_event

        camera_configs: CameraConfigs = camera_configs
        group_orchestrator: CameraGroupOrchestrator = group_orchestrator

        self._video_recorder_queue = multiprocessing.Queue()
        self._listener_process = FrameListenerProcess(
            camera_configs=camera_configs,
            group_orchestrator=group_orchestrator,
            group_shm_names=group_shm_names,
            video_recorder_queue=self._video_recorder_queue,
            frontend_pipe=frontend_pipe,
            start_recording_event=start_recording_event,
            exit_event=self._exit_event,
        )
        self._video_recorder_process = VideoRecorderProcess(
            video_recorder_queue=self._video_recorder_queue,
            frontend_pipe=frontend_pipe,
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
        self._video_recorder_process.start_process()

    def is_alive(self) -> bool:
        if self._listener_process is None or self._video_recorder_process is None:
            return False
        return self._listener_process.is_alive() and self._video_recorder_process.is_alive()

    def join(self):
        self._listener_process.join()
        self._video_recorder_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._exit_event.set()
        self._video_recorder_queue.put(None)
        if self.is_alive():
            self.join()
        self._video_recorder_queue.close()
        logger.debug(f"Frame wrangler closed")
