import logging
from multiprocessing import Queue
import multiprocessing
from multiprocessing.synchronize import Event as MultiprocessingEvent
from typing import Optional

from skellycam.core.consumers.frame_consumer_process import FrameConsumerProcess

logger = logging.getLogger(__name__)


class ConsumerManager:
    """I broke the recorder with this. The point of it is to separate the running of the process from the control of it,
    so we can close the process from outside the process. But it's not closing properly, and the camera doesn't even disconnect now (so something is blocking)
    """

    def __init__(
        self,
        exit_event: MultiprocessingEvent,
        recording_event: MultiprocessingEvent,
        display_queue: Optional[Queue] = Queue(),
        recording_queue: Optional[Queue] = Queue(),
        output_queue: Optional[Queue] = Queue(),
    ):
        self.exit_event = exit_event
        self.recording_event = recording_event
        self.display_queue = display_queue
        self.recording_queue = recording_queue
        self.output_queue = output_queue

        self.consumer_queue = Queue()

        self._process: Optional[multiprocessing.Process] = None

    def start_process(self):
        if self._process is not None and self._process.is_alive():
            self.close_process()
            # raise RuntimeError("Process is already running")  # TODO: we might not want to error here, or we need to be more careful to avoid states where this happens
            # I ran into this after "ensure cameras are ready" errored - ideally that error stops the execution and we don't get to here.

        if self.exit_event.is_set():
            self.exit_event.clear()

        self._process = self._setup_process()
        try:
            logger.debug("Frame Consumer Process starting")
            self._process.start()
        finally:
            logger.debug("Closing Frame Consumer Process")
            self.close_process()
            logger.debug("Frame Consumer Process closed")

    def close_process(self):
        if self._process and self._process.is_alive():
            self._process.join()

    def _setup_process(self) -> multiprocessing.Process:
        frame_consumer_process = FrameConsumerProcess(
            exit_event=self.exit_event,
            recording_event=self.recording_event,
            consumer_queue=self.consumer_queue,
            display_queue=self.display_queue,
            recording_queue=self.recording_queue,
            output_queue=self.output_queue,
        )

        return multiprocessing.Process(
            target=frame_consumer_process.run_process,
            name=f"FrameConsumerProcess",
        )
