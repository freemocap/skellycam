import logging
import multiprocessing
import time
from dataclasses import dataclass
from typing import Optional, List

import cv2
import numpy as np

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestrator, CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.timestamps.framerate_tracker import FrameRateTracker
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class ImageAnnotator:
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    color_top = (255, 0, 255)  # FFOOFF!
    thickness_top = 3
    color_bottom = (125, 0, 255) # 000OFF!
    thickness_bottom = 4
    position_x = 10 # top-left corner (x: left, +X is rightward)
    position_y = 50 # top-left corner (y: top, +Y is downward)
    vertical_offset = 50

    def annotate_image(self,
                       image: np.ndarray,
                       string_list: List[str],
                       multi_frame_number: int,
                       frame_number: int,
                       camera_id: int) -> np.ndarray:
        annotated_image = image.copy()
        # cv2.rectangle(annotated_image, (0, 0), (300, 80), (255, 255, 255, .2), -1)
        for _ in range(2):
            if _ == 0:
                color = self.color_top
                thickness = self.thickness_top
            else:
                color = self.color_bottom
                thickness = self.thickness_bottom
            cv2.putText(annotated_image,
                        f" CameraId: {camera_id}, Frame#{frame_number})",
                        (self.position_x, self.position_y), self.font, self.font_scale, color, thickness)

            cv2.putText(annotated_image, f"MultiFrame# {multi_frame_number}", (self.position_x, self.position_y + self.vertical_offset), self.font, self.font_scale, color, thickness)
            for i, string in enumerate(string_list):
                cv2.putText(annotated_image, string, (self.position_x, self.position_y + (i + 2) * self.vertical_offset), self.font, self.font_scale, color, thickness)
        return annotated_image


class FrameListenerProcess:
    def __init__(
            self,
            camera_group_dto: CameraGroupDTO,
            shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
            new_configs_queue: multiprocessing.Queue):
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_group_dto,
                                                      shmorc_dto,
                                                      new_configs_queue,
                                                      )
                                                )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(camera_group_dto: CameraGroupDTO,
                     shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                     new_configs_queue: multiprocessing.Queue,
                     ):
        logger.trace(f"Starting FrameListener loop...")
        shmorchestrator = CameraGroupSharedMemoryOrchestrator.recreate(camera_group_dto=camera_group_dto,
                                                                       shmorc_dto=shmorc_dto,
                                                                       read_only=False)
        frame_loop_shm = shmorchestrator.frame_loop_shm
        orchestrator = shmorchestrator.orchestrator
        multi_frame_escape_shm = shmorchestrator.multi_frame_escape_ring_shm

        framerate_tracker = FrameRateTracker()
        mf_payload: Optional[MultiFramePayload] = None
        camera_configs = camera_group_dto.camera_configs
        image_annotator = ImageAnnotator()
        try:

            while not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                if new_configs_queue.qsize() > 0:
                    camera_configs = new_configs_queue.get()

                if orchestrator.should_pull_multi_frame_from_shm.value:

                    mf_payload: MultiFramePayload = frame_loop_shm.get_multi_frame_payload(
                        previous_payload=mf_payload,
                        camera_configs=camera_configs,
                    )

                    logger.loop(
                        f"FrameListener - copied multi-frame payload# {mf_payload.multi_frame_number} from shared memory")

                    framerate_tracker.update(time.perf_counter_ns())

                    for camera_id, frame in mf_payload.frames.items():
                        frame.image = image_annotator.annotate_image(image=frame.image,
                                                                     frame_number=frame.frame_number,
                                                                     multi_frame_number=mf_payload.multi_frame_number,
                                                                     string_list=framerate_tracker.to_string_list(),
                                                                     camera_id=camera_id)

                    multi_frame_escape_shm.put_multi_frame_payload(mf_payload)
                    orchestrator.signal_multi_frame_pulled_from_shm()
                else:
                    wait_1ms()

        except Exception as e:
            logger.exception(f"Frame listener process error: {e.__class__} - {e}")
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame exporter process error: {e} - Broken pipe error, problem in FrameRouterProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            logger.info(f"Frame exporter process received KeyboardInterrupt, shutting down gracefully...")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not camera_group_dto.ipc_flags.global_kill_flag.value:
                logger.warning(
                    "FrameListenerProcess was closed before the camera group or global kill flag(s) were set.")
                camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            frame_loop_shm.close()
            multi_frame_escape_shm.close()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()
