import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.recording_manager import WorkerType
from skellycam.core.types.numpy_record_dtypes import create_multiframe_dtype
from skellycam.core.types.type_overloads import TopicSubscriptionQueue, WorkerStrategy
from skellycam.utilities.wait_functions import wait_10ms, wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class MultiframeBuilder:
    ipc: CameraGroupIPC
    close_self_flag: multiprocessing.Value
    mf_publication_thread: WorkerType

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               worker_strategy: WorkerStrategy):

        close_self_flag = multiprocessing.Value("b", False)
        mf_publication_thread = worker_strategy.value(target=cls._run_mf_publication_thread,
                                                      kwargs=dict(ipc=ipc,
                                                                  new_shm_subscription=ipc.pubsub.topics[
                                                                      TopicTypes.SHM_UPDATES].get_subscription(),
                                                                  close_self_flag=close_self_flag),
                                                      daemon=True)
        return cls(ipc=ipc,
                   mf_publication_thread=mf_publication_thread,
                   close_self_flag=close_self_flag
                   )

    @staticmethod
    def _run_mf_publication_thread(ipc: CameraGroupIPC,
                                   new_shm_subscription: TopicSubscriptionQueue,
                                   close_self_flag: multiprocessing.Value
                                   ):

        """
        Thread to publish multi-frame payloads to the shared memory.
        """
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
        def should_continue():
            return ipc.should_continue and not close_self_flag.value

        while should_continue() and new_shm_subscription.empty():
            wait_10ms()
        shm_message: SetShmMessage = new_shm_subscription.get()
        if not isinstance(shm_message, SetShmMessage):
            raise ValueError(f"Expected SetShmMessage, got {type(shm_message)}")
        shm_dto: CameraGroupSharedMemoryDTO = shm_message.camera_group_shm_dto
        camera_group_shm = CameraGroupSharedMemoryManager.recreate(shm_dto=shm_dto, read_only=False)
        logger.success(f"Starting multi-frame publication thread for camera group {ipc.group_id}...")

        # Create multiframe dtype based on camera configs
        multiframe_dtype = create_multiframe_dtype(camera_group_shm.camera_configs)
        mf_rec_array = np.recarray(1, dtype=multiframe_dtype)
        for camera_id in multiframe_dtype.names:
            mf_rec_array[camera_id].frame_metadata.camera_config[0] = camera_group_shm.camera_configs[camera_id].to_numpy_record_array()
            mf_rec_array[camera_id].frame_metadata.frame_number[0] = -1
        try:
            while should_continue():
                if ipc.should_pause.value:
                    ipc.mf_builder_status.is_paused.value = True
                    wait_10ms()
                    continue
                ipc.mf_builder_status.is_paused.value = False
                if not ipc.camera_orchestrator.all_cameras_ready:
                    wait_1ms()
                    continue
                mf_rec_array = camera_group_shm.build_all_new_multiframes(mf_rec_array)

        except Exception as e:
            logger.exception(f"Exception in multi-frame publication thread: {e}")
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"Multi-frame publication thread for camera group {ipc.group_id} exiting...")
            camera_group_shm.close()

    def close(self):
        logger.debug(f"Closing multi-frame publisher for camera group {self.ipc.group_id}...")
        self.close_self_flag.value = True
        self.mf_publication_thread.join()
        logger.debug(f"Multi-frame publisher for camera group {self.ipc.group_id} closed.")

    def start(self):
        logger.debug(f"Starting multi-frame publisher for camera group {self.ipc.group_id}...")
        self.mf_publication_thread.start()

    def is_alive(self) -> bool:
        return self.mf_publication_thread.is_alive()

    @property
    def ready(self) -> bool:
        return self.mf_publication_thread.is_alive()