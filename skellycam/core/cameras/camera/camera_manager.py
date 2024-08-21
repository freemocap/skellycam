import multiprocessing
import threading
from typing import Optional, List, Dict

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_process import CameraProcess
from skellycam.core.cameras.config.apply_config import logger
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames


class CameraManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_orchestrator: CameraGroupOrchestrator,
                 shared_memory_names: GroupSharedMemoryNames,
                 exit_event: multiprocessing.Event):
        self.exit_event = exit_event
        self.camera_configs = camera_configs
        self.shared_memory_names = shared_memory_names
        self.group_orchestrator = group_orchestrator
        self.camera_processes: Dict[CameraId, CameraProcess] = {}
        self.update_queues: Dict[CameraId, multiprocessing.Queue] = {}

        for camera_id, config in camera_configs.items():
            self.update_queues[camera_id] = multiprocessing.Queue()
            self.camera_processes[camera_id] = CameraProcess(config=config,
                                                             triggers=group_orchestrator.camera_triggers[camera_id],
                                                             shared_memory_names=shared_memory_names[camera_id],
                                                             update_queue=self.update_queues[camera_id],
                                                             exit_event=exit_event
                                                             )

    @property
    def camera_ids(self):
        return list(self.camera_configs.keys())

    def start_cameras(self):
        logger.info(f"Starting cameras: {list(self.camera_configs.keys())}")
        for camera in self.camera_processes.values():
            camera.start()
        self.group_orchestrator.await_for_cameras_ready()
        logger.success(f"Cameras {self.camera_ids} started successfully!")

    def stop_cameras(self):
        logger.info(f"Stopping cameras: {self.camera_ids} (setting exit event)")
        [camera.close() for camera in self.camera_processes.values()]
        self.exit_event.set()

    def update_cameras(self, new_configs: CameraConfigs):
        """
        Handle new camera configurations, and update the camera processes camera_group_orchestrator accordingly.

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
                logger.trace(f"Camera {camera_id} not specified in new configs, marking for closure")
                close_these_cameras.append(camera_id)
            else:
                ### Case2 - if a camera exists in `new_configs`, but `use_this_camera` is False, stop the camera
                if not new_configs[camera_id].use_this_camera:
                    logger.trace(f"Camera {camera_id} marked as not to be used in new configs, marking for closure")
                    close_these_cameras.append(camera_id)
        self._close_cameras(close_these_cameras)

        ## Step 2 - Create new cameras and update existing cameras
        for camera_id, config in new_configs.items():
            ### Case 3 - if a camera exists in `configs` and not in `self.camera_processes`, create and start the camera
            if camera_id not in self.camera_processes:
                logger.trace(f"Creating new camera: {camera_id}")
                self.update_queues[camera_id] = multiprocessing.Queue()
                self.camera_processes[camera_id] = CameraProcess(config=config,
                                                                 shared_memory_names=self.shared_memory_names[
                                                                     camera_id],
                                                                 triggers=self.group_orchestrator.camera_triggers[
                                                                     camera_id],
                                                                 update_queue=self.update_queues[camera_id],
                                                                 exit_event=self.exit_event
                                                                 )
                self.camera_processes[camera_id].start()

            ### Case4 - if a camera exists in both, update the camera's configuration if there are changes
            else:
                if config != self.camera_configs[camera_id]:
                    logger.trace(f"Updating camera {camera_id} with new config")
                    self.update_queues[camera_id].put(config)
                else:
                    logger.trace(f"Camera {camera_id} config unchanged in new configs")

    def _close_cameras(self, close_these_cameras: Optional[List[CameraId]]):
        if not close_these_cameras:
            close_these_cameras = self.camera_ids
        logger.debug(f"Closing cameras: {close_these_cameras}")

        camera_close_threads = []
        for camera_id in close_these_cameras:
            camera_close_threads.append(threading.Thread(target=self.camera_processes[camera_id].close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]
        for camera_id in close_these_cameras:
            del self.camera_processes[camera_id]
            del self.update_queues[camera_id]

        logger.trace(f"Cameras closed: {close_these_cameras}")
