import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage, RecordingInfoMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.videos.recording_manager import RecordingManager
from skellycam.core.types.numpy_record_dtypes import create_multiframe_dtype
from skellycam.core.types.type_overloads import TopicSubscriptionQueue, WorkerStrategy, WorkerType
from skellycam.utilities.wait_functions import wait_10ms, wait_1ms, wait_100ms

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
                                                                  new_shm_subscription=ipc.pubsub.topics[TopicTypes.SHM_UPDATES].get_subscription(),
                                                                  recording_info_subscription=ipc.pubsub.topics[TopicTypes.RECORDING_INFO].get_subscription()),
                                                      daemon=True)
        return cls(ipc=ipc,
                   worker=worker,
                   )

    @staticmethod
    def _run_mf_builder_loop(ipc: CameraGroupIPC,
                             new_shm_subscription: TopicSubscriptionQueue,
                                recording_info_subscription: TopicSubscriptionQueue
                             ):

        """
        Thread to publish multi-frame payloads to the shared memory.
        """
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)

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

        recording_manager: RecordingManager | None = None
        try:
            while ipc.should_continue:
                if not ipc.camera_orchestrator.all_cameras_ready:
                    wait_1ms()
                    continue

                if not recording_info_subscription.empty():
                    recording_info_message = recording_info_subscription.get(block=False)
                    if not isinstance(recording_info_message, RecordingInfoMessage):
                        raise ValueError(f"Expected SetShmMessage, got {type(recording_info_message)}")
                    # Update the shared memory with the new recording info
                    recording_manager = RecordingManager.create(recording_info=recording_info_message.recording_info,
                                                        camera_configs=camera_group_shm.camera_configs,
                                                        )
                    ipc.mf_builder_status.ready_to_record.value = True

                ipc.mf_builder_status.building_mfs_flag.value = True
                new_data, mf_rec_array, frame_metadatas = camera_group_shm.build_all_new_multiframes(mf_rec_array)
                ipc.mf_builder_status.building_mfs_flag.value = False


                if new_data:
                    for frame_medata in frame_metadatas:
                        should_record = False
                        record_bools = {}
                        for camera_id, frame_metadata in frame_medata.items():
                            record_bools[camera_id] =  frame_metadata.frame_recorded
                        if any(list(record_bools.values())) and not all(list(record_bools.values())):
                            raise ValueError(f"All cameras must either record or not record, got recording bools: {record_bools} for camera group {ipc.group_id}")
                        if all(list(record_bools.values())):
                            should_record = True
                        if should_record:
                            if recording_manager is None:
                                raise ValueError("RecordingManager is not initialized, but should be recording!")
                            ipc.mf_builder_status.is_recording.value = True
                            frame_numbers = {camera_id: md.frame_number for camera_id,  md in frame_medata.items()}
                            print(f"Logging timestamps for frame numbers: {frame_numbers}")
                            recording_manager.add_mf_metadatas(frame_metadatas)

                        else:
                            if recording_manager is not None and recording_manager.anything_recorded:
                                recording_manager.finalize_recording()
                                recording_manager = None
                                ipc.mf_builder_status.ready_to_record.value = False
                                ipc.mf_builder_status.is_recording.value = False
                else:
                    wait_10ms()
                if ipc.should_pause.value:
                    if not ipc.mf_builder_status.is_paused.value:
                        logger.trace(f"Pausing multi-frame builder for camera group {ipc.group_id}...")
                        ipc.mf_builder_status.is_paused.value = True
                        wait_100ms()
                    else: #one more loop before pausing to make sure we clear the camera buffers
                        continue
                ipc.mf_builder_status.is_paused.value = False

        except Exception as e:
            logger.exception(f"Exception in multi-frame publication thread: {e}")
            ipc.kill_everything()
            raise
        finally:
            logger.info(f"Multi-frame publication thread for camera group {ipc.group_id} exited")
            ipc.should_continue = False
            camera_group_shm.close()


    def start(self):
        logger.debug(f"Starting multi-frame publisher for camera group {self.ipc.group_id}...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def close(self):
        if self.worker.is_alive():
            logger.debug(f"Closing multi-frame publisher for camera group {self.ipc.group_id}...")
            self.ipc.should_continue = False
            self.worker.join()
        logger.success(f"Multi-frame publisher for camera group {self.ipc.group_id} closed successfully.")

    @property
    def ready(self) -> bool:
        return self.worker.is_alive()