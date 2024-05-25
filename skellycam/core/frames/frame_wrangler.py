import logging
import multiprocessing
from typing import Optional, Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

logger = logging.getLogger(__name__)


class FrameListenerProcess(multiprocessing.Process):
    def __init__(self,
                 camera_configs: CameraConfigs,
                 shm_lock: multiprocessing.Lock,
                 shared_memory_names: Dict[CameraId, str],
                 multicam_triggers: MultiCameraTriggerOrchestrator,
                 exit_event: multiprocessing.Event
                 ):
        super().__init__(name="FrameListenerProcess")
        # self._video_recorder_manager = VideoRecorderProcessManager()
        # self._recorder_queue = recorder_queue
        self._camera_configs = camera_configs
        self._shm_lock = shm_lock
        self._multi_camera_triggers = multicam_triggers
        self._shared_memory_names = shared_memory_names
        self._exit_event = exit_event

        self._payloads_received: multiprocessing.Value = multiprocessing.Value('i', 0)

    @property
    def payloads_received(self) -> int:
        return self._payloads_received.value

    def run(self):
        multi_frame_payload = MultiFramePayload.create(camera_ids=self._camera_configs.keys())
        cameras_shm = CameraSharedMemoryManager(camera_configs=self._camera_configs,
                                                lock=self._shm_lock,
                                                existing_shared_memory_names=self._shared_memory_names)
        try:
            while not self._exit_event.is_set():
                logger.loop(f"Awaiting multi-frame payload...")
                self._await_new_multi_frame(cameras_shm, multi_frame_payload)

        except Exception as e:
            logger.error(f"Error in listen_for_frames: {type(e).__name__} - {e}")
            logger.exception(e)
        logger.trace(f"Stopped listening for multi-frames")

    def _await_new_multi_frame(self, camera_shm, multi_frame_payload):
        self._multi_camera_triggers.await_copy_trigger()
        payload = camera_shm.get_multi_frame_payload(multi_frame_payload)
        self._multi_camera_triggers.set_frames_copied()
        self._handle_payload(payload)

    def _handle_payload(self, payload: MultiFramePayload):
        self._payloads_received.value += 1
        logger.loop(f"Received full multi-frame payload #{self.payloads_received}:\n {payload}")

    #     if self._is_recording:
    #         logger.loop(f"Sending payload to recorder")
    #         self._recorder_queue.put(payload)
    #
    #     if self._ws_send_bytes is not None:
    #         logger.loop(f"Sending `self._multi_frame_payload` to frontend")
    #         await self._send_frontend_payload(payload)
    #
    # async def _send_frontend_payload(self, payload: MultiFramePayload):
    #     if self._ws_send_bytes is None:
    #         raise ValueError("Websocket `send bytes` function not set!")
    #
    #     logger.loop(f"FrameWrangler - Convert multi-frame payload to frontend payload")
    #     frontend_payload = FrontendImagePayload.from_multi_frame_payload(
    #         multi_frame_payload=payload,
    #     )
    #     logger.loop(f"FrameWrangler - Sending frontend payload: {frontend_payload}")
    #     await self._ws_send_bytes(frontend_payload.to_msgpack())


class FrameWrangler:
    def __init__(self, exit_event: multiprocessing.Event):
        super().__init__()
        self._exit_event = exit_event

        self._camera_configs: Optional[CameraConfigs] = None
        self._shm_lock: Optional[multiprocessing.Lock] = None
        self._multicam_triggers: Optional[MultiCameraTriggerOrchestrator] = None
        self._shared_memory_names: Optional[Dict[CameraId, str]] = None

        self._listener_process: Optional[FrameListenerProcess] = None

    @property
    def payloads_received(self) -> Optional[int]:
        if self._listener_process is None:
            return None
        return self._listener_process.payloads_received

    def set_camera_info(self,
                        camera_configs: CameraConfigs,
                        shm_lock: multiprocessing.Lock,
                        shared_memory_names: Dict[CameraId, str],
                        multicam_triggers: MultiCameraTriggerOrchestrator,
                        ):
        logger.debug(f"Setting camera configs to {camera_configs}")

        self._camera_configs = camera_configs
        self._shm_lock = shm_lock
        self._multicam_triggers = multicam_triggers
        self._shared_memory_names = shared_memory_names

    def start_frame_listener(self):
        logger.debug(f"Starting frame listener process...")

        self._listener_process = FrameListenerProcess(camera_configs=self._camera_configs,
                                                      shm_lock=self._shm_lock,
                                                      multicam_triggers=self._multicam_triggers,
                                                      shared_memory_names=self._shared_memory_names,
                                                      exit_event=self._exit_event)
        self._listener_process.start()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._exit_event.set()
        if self._listener_process is not None:
            self._listener_process.join()
