import logging
import multiprocessing
from typing import Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.frontend_image_payload import FrontendImagePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            group_shm_names: GroupSharedMemoryNames,
            group_orchestrator: CameraGroupOrchestrator,
            exit_event: multiprocessing.Event,
    ):
        super().__init__()
        self._payloads_received: multiprocessing.Value = multiprocessing.Value("i", 0)
        self._exit_event = exit_event

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_configs,
                                                      group_shm_names,
                                                      group_orchestrator,
                                                      self._payloads_received,
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
                     exit_event: multiprocessing.Event):
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        from skellycam.api.client.client_singleton import get_client
        client = get_client()
        logger.api(f"Connecting to client websocket...")
        client.ws_client.connect()
        try:

            logger.trace(f"Frame listener process started")
            group_orchestrator.await_for_cameras_ready()
            mf_payload: Optional[MultiFramePayload] = None

            # Frame listener loop
            while not exit_event.is_set():
                if group_orchestrator.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")
                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload)
                    group_orchestrator.set_frames_copied()
                    payloads_received.value += 1
                    fe_payload = FrontendImagePayload.from_multi_frame_payload(mf_payload)
                    client.ws_client.send_message(fe_payload.model_dump())
                else:
                    wait_1ms()

        finally:
            logger.trace(f"Stopped listening for multi-frames")
            camera_group_shm.close()  # close but don't unlink - parent process will unlink

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()


class FrameWrangler:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_shm_names: GroupSharedMemoryNames,
                 group_orchestrator: CameraGroupOrchestrator,
                 exit_event: multiprocessing.Event):
        super().__init__()
        self._exit_event = exit_event

        camera_configs: CameraConfigs = camera_configs
        group_orchestrator: CameraGroupOrchestrator = group_orchestrator

        self._listener_process = FrameListenerProcess(
            camera_configs=camera_configs,
            group_orchestrator=group_orchestrator,
            group_shm_names=group_shm_names,
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

    def is_alive(self) -> bool:
        if self._listener_process is None:
            return False
        return self._listener_process.is_alive()

    def join(self):
        self._listener_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._exit_event.set()
        if self.is_alive():
            self.join()
