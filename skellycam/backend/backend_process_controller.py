import logging
import multiprocessing
from typing import Dict, Any

import cv2
import numpy as np
from PyQt6.QtCore import QByteArray, QBuffer
from PyQt6.QtGui import QImage

from skellycam.backend.charuco.charuco_detection import draw_charuco_on_image
from skellycam.backend.opencv.group.camera_group import CameraGroup
from skellycam.data_models.camera_config import CameraConfig
from skellycam.data_models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class BackendProcessController:
    def __init__(self,
                 camera_configs: Dict[str, CameraConfig],
                 send_to_frontend,  # pipe connection
                 receive_from_frontend,  # pipe connection
                 exit_event: multiprocessing.Event):

        self._send_to_frontend = send_to_frontend
        self._receive_from_frontend = receive_from_frontend

        self._exit_event = exit_event

        self._process = multiprocessing.Process(target=self._run_camera_group_process,
                                                args=(camera_configs,
                                                      self._send_to_frontend,
                                                      self._receive_from_frontend,
                                                      self._exit_event))

    def start_camera_group_process(self):
        self._process.start()
        logger.info(f"Started camera group process")

    @staticmethod
    def _run_camera_group_process(camera_configs: Dict[str, CameraConfig],
                                  send_to_frontend,  # pipe connection
                                  receive_from_frontend,  # pipe connection
                                  exit_event: multiprocessing.Event,
                                  annotate_images: bool = False):
        camera_group = None
        try:
            logger.info(f"Starting camera group process for cameras: {camera_configs.keys()}")
            camera_group = create_and_start_camera_group(camera_configs=camera_configs,
                                                         exit_event=exit_event,
                                                         send_to_frontend=send_to_frontend)

            while camera_group.is_capturing and not exit_event.is_set():
                if receive_from_frontend.poll():
                    message = receive_from_frontend.recv()
                    logger.trace(f"Got message from frontend: `{message['type']}`")

                    handle_message_from_frontend(camera_group=camera_group,
                                                 message=message,
                                                 send_to_frontend=send_to_frontend,
                                                 annotate_images=annotate_images)


        except Exception as e:
            logger.error(f"Error in `run_camera_group_process`: {e}")
            logger.exception(e)
            send_to_frontend.send({"type": "error",
                                   "error": e})
        finally:
            if hasattr(camera_group, "close"):
                logger.info("Closing camera group")
                camera_group.close()
                send_to_frontend.send({"type": "cameras_closed"})
            logger.info("Camera group process closing down...")


def create_and_start_camera_group(camera_configs: Dict[str, CameraConfig],
                                  exit_event: multiprocessing.Event,
                                  send_to_frontend) -> CameraGroup:
    camera_group = CameraGroup(camera_configs=camera_configs)
    send_to_frontend.send({"type": "camera_group_created",
                           "camera_config_dictionary": camera_group.camera_config_dictionary})
    camera_group.start(exit_event=exit_event)

    logger.info("Emitting `cameras_connected_signal`")
    send_to_frontend.send({"type": "cameras_connected"})

    return camera_group


def handle_message_from_frontend(camera_group: CameraGroup,
                                 message: Dict[str, Any],
                                 send_to_frontend,  # pipe connection
                                 annotate_images: bool):
    logger.info(f"Handling  message: `{message['type']}`...")

    if message["type"] == "update_camera_settings":
        logger.debug(f"Updating camera settings: {message['camera_configs']}")
        _handle_update_camera_settings_message(camera_group, message, send_to_frontend)

    elif message["type"] == "start_recording":
        logger.info(f"Starting recording with name: {message['recording_name']}")
        # camera_group.start_recording(recording_name=message["recording_name"])
        raise NotImplementedError()

    elif message["type"] == "stop_recording":
        logger.info(f"Received message: {message['type']}")
        raise NotImplementedError()

    elif message["type"] == "get_latest_frames":
        logger.trace(f"Getting latest frames...")
        latest_frames = camera_group.latest_frames()
        if latest_frames is None:
            logger.trace(f"No frames yet...")
        else:
            send_image_to_frontend(annotate_images=annotate_images,
                                   frames=camera_group.latest_frames(),
                                   send_to_frontend=send_to_frontend)
    else:
        raise ValueError(f"Unknown message type: {message['type']}")


def _handle_update_camera_settings_message(camera_group, message, send_to_frontend):
    logger.debug(f"Updating camera_configs: {message['camera_configs']}")
    try:
        camera_group.update_camera_configs(message["camera_configs"])
        send_to_frontend.send({"type": "camera_settings_updated"})
    except Exception as e:
        logger.error(f"Error updating camera settings: {e}")
        send_to_frontend.send({"type": "error",
                               "error": e})


def send_image_to_frontend(annotate_images: bool,
                           frames: Dict[str, FramePayload],
                           send_to_frontend):
    for camera_id, frame_payload in frames.items():
        image = prepare_image_for_frontend(image=frame_payload.image,
                                           annotate_image=annotate_images)
        byte_array = _convert_image_to_byte_array(image)
        send_to_frontend.send({"type": "new_image",
                               "image": byte_array,
                               "frame_info": {"camera_id": frame_payload.camera_id,
                                              "timestamp_ns": frame_payload.timestamp_ns,
                                              "number_of_frames_received": frame_payload.number_of_frames_received}})


def _convert_image_to_byte_array(image):
    # Convert the numpy image to a QPixmap
    height, width, channel = image.shape
    bytes_per_line = 3 * width
    q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
    # Convert the QPixmap to a QByteArray then a QBuffer
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    q_image.save(buffer, format="JPEG")  # write the image to the buffer in jpg format, which goes to the byte array
    return byte_array


def prepare_image_for_frontend(image: np.ndarray,
                               annotate_image: bool,
                               target_size=(960, 540)) -> np.ndarray:
    if annotate_image:
        image = draw_charuco_on_image(image)

    # convert color
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # Find the ratio of the new height to the old one
    ratio = target_size[1] / image.shape[0]
    # Preserve aspect ratio.
    width = int(image.shape[1] * ratio)

    dimension = (width, target_size[1])
    # resize image
    image_scaled = cv2.resize(image, dimension, interpolation=cv2.INTER_AREA)

    return image_scaled
