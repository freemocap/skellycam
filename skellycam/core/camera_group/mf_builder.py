import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage, FramerateMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.framerate_tracker import FramerateTracker, FRAMERATE_UPDATE_INTERVAL
from skellycam.core.types.numpy_record_dtypes import create_multiframe_dtype
from skellycam.core.types.type_overloads import TopicSubscriptionQueue, WorkerStrategy, WorkerType
from skellycam.utilities.wait_functions import wait_10ms, wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class MultiframeBuilder:
    ipc: CameraGroupIPC
    worker: WorkerType

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               worker_strategy: WorkerStrategy):

        worker = worker_strategy.value(target=cls._run_mf_builder_loop,
                                       kwargs=dict(ipc=ipc,
                                                   new_shm_subscription=ipc.pubsub.topics[TopicTypes.SHM_UPDATES].get_subscription()),
                                       daemon=True)
        return cls(ipc=ipc,
                   worker=worker,
                   )

    @staticmethod
    def _run_mf_builder_loop(ipc: CameraGroupIPC,
                             new_shm_subscription: TopicSubscriptionQueue,
                             ):

        """
        Thread to publish multi-frame payloads to the shared memory.
        """
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
        ipc.mf_builder_status.is_running.value = True
        camera_group_shm:CameraGroupSharedMemoryManager|None = None
        while ipc.should_continue:
            try:
                if new_shm_subscription.empty():
                    wait_10ms()
                    continue

                shm_message = new_shm_subscription.get(block=False)
                if not isinstance(shm_message, SetShmMessage):
                    raise ValueError(f"Expected SetShmMessage, got {type(shm_message)}")
                shm_dto: CameraGroupSharedMemoryDTO = shm_message.camera_group_shm_dto
                camera_group_shm = CameraGroupSharedMemoryManager.recreate(shm_dto=shm_dto, read_only=False)
                logger.info(f"Initialized shared memory for camera group {ipc.group_id} with {len(camera_group_shm.camera_configs)} cameras in multi-frame builder.")
                break
            except Exception as e:
                if not ipc.should_continue:
                    logger.info(
                        f"Exiting multi-frame builder loop during initialization for camera group {ipc.group_id}")
                    return
                logger.error(f"Error initializing multi-frame builder: {e}")
        # If we couldn't initialize the shared memory and we're shutting down, exit gracefully
        if camera_group_shm is None:
            logger.error(f"Failed to initialize shared memory for camera group {ipc.group_id}")
            ipc.kill_everything()
            return

        # Create multiframe dtype based on camera configs
        multiframe_dtype = create_multiframe_dtype(camera_group_shm.camera_configs)
        mf_rec_array = np.recarray(1, dtype=multiframe_dtype)
        for camera_id in multiframe_dtype.names:
            mf_rec_array[camera_id].frame_metadata.camera_config[0] = camera_group_shm.camera_configs[camera_id].to_numpy_record_array()
            mf_rec_array[camera_id].frame_metadata.frame_number[0] = -1

        last_sent_framerate_timestamp = time.perf_counter()
        try:
            framerate_tracker = FramerateTracker.create(framerate_source=f"CameraGroup-{ipc.group_id}")
            while ipc.should_continue:
                if not ipc.camera_orchestrator.all_cameras_ready:
                    wait_1ms()
                    continue

                ipc.mf_builder_status.building_mfs_flag.value = True
                new_data, mf_rec_array,framerate_tracker = camera_group_shm.build_all_new_multiframes(mf_rec_array=mf_rec_array,framerate_tracker=framerate_tracker)
                ipc.mf_builder_status.building_mfs_flag.value = False

                if time.perf_counter() - last_sent_framerate_timestamp > FRAMERATE_UPDATE_INTERVAL:
                    ipc.pubsub.topics[TopicTypes.FRAMERATE].publish(FramerateMessage(current_framerate=framerate_tracker.current_framerate), overwrite=True)
                    framerate_tracker.clear()
                    last_sent_framerate_timestamp = time.perf_counter()

                if not new_data:
                    wait_1ms()
                    continue

                # tik = time.perf_counter_ns()
                # print(f"Multi-frame builder for camera group {ipc.group_id} built new multi-frame in {(tik - previous_tik) / 1e6} ms and got {len(new_data)} new multi-frames")
                # previous_tik = tik


        except Exception as e:
            logger.exception(f"Exception in multi-frame publication thread: {e}")
            ipc.kill_everything()
            raise
        finally:
            camera_group_shm.close()
            ipc.mf_builder_status.is_running.value = False
            ipc.mf_builder_status.closed.value = True
            logger.info(f"Multi-frame publication thread for camera group {ipc.group_id} exited")



    def start(self):
        logger.debug(f"Starting multi-frame publisher for camera group {self.ipc.group_id}...")
        self.worker.start()


    @property
    def is_alive(self) -> bool:
        return not self.ipc.mf_builder_status.closed.value
