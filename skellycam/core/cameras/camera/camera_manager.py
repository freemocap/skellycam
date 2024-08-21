import multiprocessing
import threading
from typing import Dict

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_process import CameraProcess
from skellycam.core.cameras.config.apply_config import logger
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames


class CameraManager(BaseModel):
    camera_configs: CameraConfigs
    shared_memory_names: GroupSharedMemoryNames
    exit_event: multiprocessing.Event

    camera_processes: Dict[CameraId, CameraProcess] = Field(default_factory=dict)
    update_queues: Dict[CameraId, multiprocessing.Queue] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               shared_memory_names: GroupSharedMemoryNames,
               exit_event: multiprocessing.Event):
        camera_processes = {}
        update_queues = {}
        for camera_id, config in camera_configs.items():
            update_queues[camera_id] = multiprocessing.Queue()
            camera_processes[camera_id] = CameraProcess(config=config,
                                                        shared_memory_names=shared_memory_names[camera_id],
                                                        update_queue=update_queues[camera_id],
                                                        exit_event=exit_event
                                                        )

        return cls(
            camera_configs=camera_configs,
            shared_memory_names=shared_memory_names,
            exit_event=exit_event
        )

    def start_cameras(self):
        logger.info(f"Starting cameras: {list(self.camera_configs.keys())}")
        for camera in self.camera_processes.values():
            camera.start()

    def stop_cameras(self):
        logger.info(f"Stopping cameras: {list(self.camera_configs.keys())} (setting exit event)")
        self.exit_event.set()

    def update_cameras(self, new_configs: CameraConfigs):
        """
        Handle new camera configurations, and update the camera processes accordingly.

        Step 1 - Close/delete cameras that are no longer needed
        Step 2 - Create new cameras and update existing cameras

        # Case1 - if a camera exists in `self.camera_processes` and not in `new_configs`, stop the camera
        # Case2 - if a camera exists in new_configs, but `use_this_camera` is False, stop the camera
        # Case3 - if a camera exists in `configs` and not in `self.camera_processes`, create and start the camera
        # Case4 - if a camera exists in both, update the camera's configuration
        """

        ## Step 1 - Close/delete cameras that are no longer needed
        ### Case1 - if a camera exists in `self.camera_processes` and not in `new_configs`, stop the camera
        close_these_cameras = []
        for camera_id in self.camera_processes.keys():
            if camera_id not in new_configs:
                close_these_cameras.append(camera_id)
            else:
                ### Case2 - if a camera exists in `new_configs`, but `use_this_camera` is False, stop the camera
                if new_configs[camera_id].use_this_camera == False:
                    close_these_cameras.append(camera_id)
        camera_close_threads = []
        for camera_id in close_these_cameras:
            camera_close_threads.append(threading.Thread(target=self.camera_processes[camera_id].close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]
        for camera_id in close_these_cameras:
            del self.camera_processes[camera_id]
            del self.update_queues[camera_id]

        ## Step 2 - Create new cameras and update existing cameras
        for camera_id, config in new_configs.items():
            ### Case 3 - if a camera exists in `configs` and not in `self.camera_processes`, create and start the camera
            if camera_id not in self.camera_processes:
                self.update_queues[camera_id] = multiprocessing.Queue()
                self.camera_processes[camera_id] = CameraProcess(config=config,
                                                                 shared_memory_names=self.shared_memory_names[
                                                                     camera_id],
                                                                 update_queue=self.update_queues[camera_id],
                                                                 exit_event=self.exit_event
                                                                 )
                self.camera_processes[camera_id].start()

            ### Case4 - if a camera exists in both, update the camera's configuration if there are changes
            else:
                self.update_queues[camera_id].put(config)
