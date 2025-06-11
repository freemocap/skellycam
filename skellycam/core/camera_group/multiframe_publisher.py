import enum
import logging
import multiprocessing
import threading
from copy import deepcopy
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateShmMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.types import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class MultiframeBuilderWorkerStrategies(enum.Enum):
    THREAD = enum.auto()
    PROCESS = enum.auto()


@dataclass
class MultiframeBuilder:
    worker: multiprocessing.Process | threading.Thread
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO,
               worker_strategy: MultiframeBuilderWorkerStrategies = MultiframeBuilderWorkerStrategies.THREAD
               ) -> 'MultiframeBuilder':
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
                                          shm_update_subscription=ipc.pubsub.topics[
                                              TopicTypes.SHM_UPDATES].get_subscription(),
                                          )
                              )

        return cls(worker=worker,
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
                         shm_update_subscription: TopicSubscriptionQueue,
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
                if not shm_update_subscription.empty():
                    update_shm_message = shm_update_subscription.get()
                    camera_group_shm.build_all_new_multiframes(previous_payload=latest_mf,
                                                               overwrite=False)
                    camera_group_shm.close()
                    camera_group_shm = CameraGroupSharedMemoryManager.recreate(
                        shm_dto=update_shm_message.group_shm_dto,
                        read_only=False)
                    if not isinstance(update_shm_message, UpdateShmMessage):
                        raise TypeError(f"Received unexpected message type: {type(update_shm_message)}")
                if latest_mf and not all([config.camera_id in latest_mf.camera_configs and latest_mf.camera_configs[
                    config.camera_id] == config for config in ipc.camera_configs.values()]):
                    logger.trace(f"Camera configurations have changed, re-building multi-frames: \n {[ latest_mf.camera_configs[config.camera_id]-config for config in ipc.camera_configs.values()]}")
                    latest_mf.camera_configs = ipc.camera_configs
                    camera_group_shm.build_all_new_multiframes(previous_payload=latest_mf,
                                                               overwrite=True)


                latest_mfs = camera_group_shm.build_all_new_multiframes(previous_payload=latest_mf,
                                                                        overwrite=False)
                ipc.mf_publisher_status.total_frames_published.value += len(latest_mfs)
                ipc.mf_publisher_status.number_frames_published_this_cycle.value = len(latest_mfs)
                if latest_mfs:
                    latest_mf = latest_mfs[-1]

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
