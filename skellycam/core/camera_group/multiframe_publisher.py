import enum
import logging
import multiprocessing
import threading
import time
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateShmMessage, FrontendPayloadTopic, FrontendPayloadMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.types import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_10ms, wait_30ms, wait_1ms

logger = logging.getLogger(__name__)

class MultiframeBuilderWorkerStrategies(enum.Enum):
    THREAD = enum.auto()
    PROCESS = enum.auto()
@dataclass
class MultiframeBuilder:
    worker: multiprocessing.Process
    ipc: CameraGroupIPC
    fe_payload_subscription: TopicSubscriptionQueue
    _latest_fe_payload: FrontendFramePayload | None = None

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO,
               worker_strategy: MultiframeBuilderWorkerStrategies = MultiframeBuilderWorkerStrategies.THREAD
               ) -> 'MultiframeBuilder':
        fe_subscription = ipc.pubsub.topics[TopicTypes.FRONTEND_PAYLOAD].get_subscription()
        if worker_strategy == MultiframeBuilderWorkerStrategies.PROCESS:
            worker_maker = multiprocessing.Process
        elif worker_strategy == MultiframeBuilderWorkerStrategies.THREAD:
            worker_maker = threading.Thread
        else:
            raise ValueError(f"Unsupported camera worker strategy: {worker_strategy}")

        worker = worker_maker(target=cls._mf_builder_loop,
                                             name=f"{cls.__class__.__name__}-Builder",
                                             kwargs=dict(ipc=ipc,
                                                         group_shm_dto=group_shm_dto,
                                                         update_shm_sub_queue=ipc.pubsub.topics[
                                                             TopicTypes.SHM_UPDATES].get_subscription(),
                                                         frontend_payload_topic=ipc.pubsub.topics[
                                                             TopicTypes.FRONTEND_PAYLOAD],
                                                         )
                                             )

        return cls(worker=worker,
                   fe_payload_subscription=fe_subscription,
                   ipc=ipc,
                   )

    def start(self):
        logger.debug(f"Starting multi-frame publication process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self):
        self.worker.join()

    def close(self):
        logger.debug(f"Closing multi-frame publication process...")
        self.ipc.should_continue = False
        if self.is_alive():
            self.join()
        logger.debug(f"Multiframe publisher closed")

    @staticmethod
    def _mf_builder_loop(ipc: CameraGroupIPC,
                         group_shm_dto: CameraGroupSharedMemoryDTO,
                         frontend_payload_topic: FrontendPayloadTopic,
                         update_shm_sub_queue: TopicSubscriptionQueue,
                         ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication, )
        camera_group_shm: CameraGroupSharedMemoryManager = CameraGroupSharedMemoryManager.recreate(
            shm_dto=group_shm_dto,
            read_only=False)

        latest_mf: MultiFramePayload | None = None
        ipc.mf_publisher_status.is_running_flag.value = True
        logger.success(f"Multiframe Publication process started")
        try:
            while ipc.should_continue:
                wait_1ms()
                if not update_shm_sub_queue.empty():
                    update_shm_message = update_shm_sub_queue.get()
                    if not isinstance(update_shm_message, UpdateShmMessage):
                        raise TypeError(f"Received unexpected message type: {type(update_shm_message)}")

                if ipc.should_pause_flag.value:
                    logger.debug(f"Multiframe publication process paused for camera group {ipc.group_id}")
                    ipc.mf_publisher_status.is_paused_flag.value = True
                    while ipc.should_pause_flag.value and ipc.should_continue:
                        wait_10ms()
                        continue
                ipc.mf_publisher_status.is_paused_flag.value = False

                latest_mfs = camera_group_shm.build_all_new_multiframes(previous_payload=latest_mf,
                                                                        overwrite=True)
                ipc.mf_publisher_status.total_frames_published.value += len(latest_mfs)
                ipc.mf_publisher_status.number_frames_published_this_cycle.value = len(latest_mfs)
                if latest_mfs:
                    # logger.loop(f"Published {len(latest_mfs)} new multi-frames")
                    latest_mf = latest_mfs[-1]
                    # if ipc.main_process_backpressure.value <= 1:
                    #     latest_fe = FrontendFramePayload.from_multi_frame_payload(
                    #         multi_frame_payload=latest_mf)
                    #     latest_fe.multi_frame_metadata.before_publication_timestamp_ns = time.perf_counter_ns()
                        # frontend_payload_topic.publish(FrontendPayloadMessage(frontend_payload=latest_fe), overwrite=True)

        except Exception as e:
            ipc.kill_everything()
            logger.error(f"Process error: {e}")
            logger.exception(e)
            ipc.mf_publisher_status.error.value = True
            raise
        except KeyboardInterrupt:
            pass
        finally:
            camera_group_shm.close()
            logger.debug(f"Multiframe publication process completed")
            ipc.mf_publisher_status.is_running_flag.value = False

