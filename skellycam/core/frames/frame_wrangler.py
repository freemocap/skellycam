import logging
import multiprocessing
import time
from multiprocessing.synchronize import Event as MultiprocessingEvent
from typing import Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import (
    CameraGroupOrchestrator,
)
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.utilities.wait_functions import wait_1ms


logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
        self,
        camera_configs: CameraConfigs,
        group_shm_names: GroupSharedMemoryNames,
        group_orchestrator: CameraGroupOrchestrator,
        consumer_queue: multiprocessing.Queue,
        exit_event: MultiprocessingEvent,
    ):
        super().__init__()
        self._payloads_received: multiprocessing.Value = multiprocessing.Value("i", 0)
        self._exit_event = exit_event

        self._process = multiprocessing.Process(
            target=self._run_process,
            name=self.__class__.__name__,
            args=(
                camera_configs,
                group_shm_names,
                group_orchestrator,
                self._payloads_received,
                consumer_queue,
                exit_event,
            ),
        )

    @property
    def payloads_received(self) -> int:
        return self._payloads_received.value

    def start_process(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(
        camera_configs: CameraConfigs,
        group_shm_names: GroupSharedMemoryNames,
        group_orchestrator: CameraGroupOrchestrator,
        payloads_received: multiprocessing.Value,
        consumer_queue: multiprocessing.Queue,  # TODO: include this in tests
        exit_event: MultiprocessingEvent,
    ):
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        try:

            logger.trace(f"Frame listener process started")
            group_orchestrator.await_for_cameras_ready()
            payload: Optional[MultiFramePayload] = None

            # Frame listener loop
            while not exit_event.is_set():
                if group_orchestrator.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")
                    payload = camera_group_shm.get_multi_frame_payload(
                        previous_payload=payload
                    )
                    group_orchestrator.set_frames_copied()
                    payloads_received.value += 1
                    # how long does this take? should be 33ish ms, lower is better
                    # time this on different configs, how fast is it on 3 cameras at 1080p?
                    # only if needed, could potentially send bytes over pipe

                    # right now we're "paying the pickle price twice"
                    # if needed we could keep dtos until we send over pipe, then put into multiframe payload later

                    payload.set_timestamps(
                        metadata_index=FRAME_METADATA_MODEL.PRE_QUEUE_TIMESTAMP_NS.value,
                        timestamp_ns=time.perf_counter_ns(),
                    )
                    consumer_queue.put(payload)
                else:
                    wait_1ms()

        finally:
            logger.trace(f"Stopped listening for multi-frames after {payloads_received.value} frames")
            camera_group_shm.close()  # close but don't unlink - parent process will unlink

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()


class FrameWrangler:
    def __init__(
        self,
        camera_configs: CameraConfigs,
        group_shm_names: GroupSharedMemoryNames,
        group_orchestrator: CameraGroupOrchestrator,
        consumer_queue: multiprocessing.Queue,  # TODO: include this in tests
        exit_event: MultiprocessingEvent,
    ):
        super().__init__()
        self._exit_event = exit_event

        self._listener_process = FrameListenerProcess(
            camera_configs=camera_configs,
            group_orchestrator=group_orchestrator,
            group_shm_names=group_shm_names,
            consumer_queue=consumer_queue,
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
