import asyncio
import logging
import multiprocessing
import sys
import time
from statistics import mean, median
from multiprocessing import Queue
from multiprocessing.synchronize import Event as MultiprocessingEvent
from queue import Empty, Full
from typing import Optional

from skellycam.core.consumers.frontend.frontend_image_payload import (
    FrontendImagePayload,
)
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.system.logging_configuration.custom_formatter import CustomFormatter
from skellycam.system.logging_configuration.logger_builder import LoggerBuilder
from skellycam.system.logging_configuration.queue_logger import DirectQueueHandler
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameConsumerProcess:
    """
    Consumes frames from the consumer queue, and spits them out into destination queues (display, recording, output)

    Probably want to run in its own process, but still figuring out details of that
    """

    def __init__(
        self,
        exit_event: MultiprocessingEvent,
        consumer_queue: Queue = Queue(),
        display_queue: Optional[Queue] = Queue(),
        recording_queue: Optional[Queue] = Queue(),
        output_queue: Optional[Queue] = Queue(),
    ):
        self.exit_event = exit_event
        self.consumer_queue = consumer_queue
        self.display_queue = display_queue
        self.recording_queue = recording_queue
        self.output_queue = output_queue

        self.logging_queue = multiprocessing.Queue()
        self._process = None

    def start_process(self):
        if self._process is not None and self._process.is_alive():
            raise RuntimeError("Process is already running")

        self._process = self._setup_process()
        self._process.start()

    def close(self):
        self.exit_event.set()
        # we need the display + output queues to be empty in order for the process to join, and don't care if the last frames aren't displayed/output
        # we need the recording queue to empty itself though, as we can't don't want to miss recording frames

        # TODO: need to verify this, this is just what I needed when I prototyped a shm based camera system
        if self.display_queue:
            self.display_queue.close()
            self.display_queue.cancel_join_thread()

        if self.output_queue:
            self.output_queue.close()
            self.output_queue.cancel_join_thread()

        if self._process.is_alive():
            self._process.join()

    def _pull_from_queue(self):
        times_across_queue = []
        while not self.exit_event.is_set():
            try: 
                multiframe_payload: MultiFramePayload = self.consumer_queue.get()

                if multiframe_payload is None or multiframe_payload.frames is None:
                    continue

                multiframe_payload.set_timestamps(
                    metadata_index=FRAME_METADATA_MODEL.POST_QUEUE_TIMESTAMP_NS.value,
                    timestamp_ns=time.perf_counter_ns(),
                )

                if (single_payload := next(iter(multiframe_payload.frames.values()))):
                    metadata_array = single_payload.metadata

                time_across_queue = (metadata_array[FRAME_METADATA_MODEL.POST_QUEUE_TIMESTAMP_NS.value] - metadata_array[FRAME_METADATA_MODEL.PRE_QUEUE_TIMESTAMP_NS.value]) / 1e6
                times_across_queue.append(time_across_queue)
                # print(f"time across queue in ms: {time_across_queue:.2f}")

                # need to consider cost of queueing/enqueuing here
                # could we pickle here, and the shove the pickle into each queue

                # task 1
                # if self.recording_queue:
                #     self.recording_queue.put(multiframe_payload) # don't use put_nowait here, because we don't want to skip recording any frames

                # # task 2
                # if self.display_queue:
                #     frontend_payload = FrontendImagePayload.from_multi_frame_payload(
                #         multi_frame_payload=multiframe_payload
                #     )
                #     # this should be sent over websocket
                #     # images should be compressed to Base64 JPEG strings
                #     try:
                #         self.display_queue.put_nowait(frontend_payload)
                #     except Full:
                #         pass

                # if self.output_queue:
                #     try:
                #         self.output_queue.put_nowait(multiframe_payload)
                #     except Full:
                #         pass

            except Empty:
                wait_1ms()
            except Exception as e:
                logger.exception(e)
            finally:    
                logger.info(f"\tFrame payloads received from consumer queue: {len(times_across_queue)}"
                    f"\n\tAverage time across queue (ms): {mean(times_across_queue):.2f}"
                    f"\n\tMedian time across queue (ms): {median(times_across_queue):.2f}"
                    f"\n\tFirst ten times across queue (ms): {times_across_queue[:10]}")
        # once exit event is set, we still need to empty recording queue to make sure we don't miss frames
                
    def _setup_process(self) -> multiprocessing.Process:
        return multiprocessing.Process(target=self._run_process,
                                                name=f"FrameConsumerProcess",
                                                )
                
    def _run_process(self):
        handler = DirectQueueHandler(self.logging_queue)
        self.default_logging_formatter = CustomFormatter(
            fmt=LoggerBuilder.format_string, datefmt="%Y-%m-%dT%H:%M:%S"
        )
        logger.addHandler(handler)

        self._pull_from_queue()

    # TODO: this wasn't working, but I've fixed a lot since I wrote it so maybe it will?
    async def monitor_logging_queue(self):
        while self._process.is_alive():
            await asyncio.sleep(0.1)
            while not self.logging_queue.empty():
                record = self.logging_queue.get()
                logger.info(f"{record.msg}")  #TODO: we should be able to replace defaulting to "info" by accessing record.levelno

        while not self.logging_queue.empty():
            record = self.logging_queue.get()
            logger.info(f"{record.msg}")

        logger.debug("Finished monitoring consumer process")
