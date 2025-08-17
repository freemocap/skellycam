import logging

import cv2
import numpy as np

from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import ONE_MEGABYTE, ONE_KILOBYTE
from skellycam.core.types.numpy_record_dtypes import JPEG_ENCODING_PARAMETERS, logger, \
    FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE, FRONTEND_FRAME_HEADER_DTYPE
from skellycam.core.types.type_overloads import FrameNumberInt, MultiframeTimestampFloat
_reusable_bytes_payload: bytearray = bytearray(0)  # Will be resized to fit the payload size in runtime


def create_frontend_payload_from_mf_recarray(mf_rec_array: np.recarray,
                                             display_image_sizes: dict[str, dict[str, float]] | None = None,
                                             jpeg_encoding_parameters=None) -> tuple[FrameNumberInt, MultiframeTimestampFloat,bytes]:
    """
    Convert a multi-frame record array into a list of record arrays for each camera.
     first element is the header, which tell the frontend how many cameras are in the payload.
     then for each camera, we send a frame metadata record array (including the length of the JPEG string), followed by the JPEG image data.
     We end with a footer record array that indicates the end of the payload, allowing verification that all data was received correctly.

    We then convert that list into a bytes object for websocket transmission.
    """
    global _reusable_bytes_payload
    if jpeg_encoding_parameters is None:
        jpeg_encoding_parameters = JPEG_ENCODING_PARAMETERS

    camera_ids = mf_rec_array.dtype.names
    frame_numbers = [mf_rec_array[camera_id].frame_metadata.frame_number[0] for camera_id in camera_ids]
    if len(set(frame_numbers)) != 1:
        raise ValueError("All cameras in the multi-frame record array must have the same frame number.")
    frame_number = frame_numbers[0]
    number_of_cameras = len(camera_ids)

    # Pre-allocate approximate size to avoid reallocations
    estimated_size = (number_of_cameras + 1) * ONE_MEGABYTE

    # Reuse existing bytearray if it's large enough, otherwise resize it
    if len(_reusable_bytes_payload) < estimated_size:
        if len(_reusable_bytes_payload) > 0:
            logger.warning(
                f"Reusable bytes payload size ({len(_reusable_bytes_payload)} bytes) is smaller than estimated size ({estimated_size} bytes), resizing.")
        logger.debug(f"Set reusable bytes payload to {estimated_size // ONE_KILOBYTE} kilobytes")
        _reusable_bytes_payload = bytearray(estimated_size)

    # Reset position counter
    current_pos = 0

    # Add header
    payload_header = np.array([(0, frame_number, number_of_cameras)],
                              dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    header_bytes = payload_header.tobytes()

    _reusable_bytes_payload[current_pos:current_pos + len(header_bytes)] = header_bytes
    current_pos += len(header_bytes)
    # image_scale= np.min([np.max([(len(camera_ids)*2)**-1, 0.2]), 1.0])
    image_scale= .5
    frame_timestamps:list[int] = []
    for camera_id in camera_ids:
        frame_recarray = mf_rec_array[camera_id][0]
        frame_timestamps.append(np.mean([frame_recarray.frame_metadata.timestamps.pre_frame_grab_ns,
                                         frame_recarray.frame_metadata.timestamps.post_frame_grab_ns]))

        if frame_recarray.frame_metadata.camera_config.rotation != -1:
            rotated_image = cv2.rotate(frame_recarray.image[:], frame_recarray.frame_metadata.camera_config.rotation)
        else:
            rotated_image = frame_recarray.image[:]

        if display_image_sizes is None or camera_id not in display_image_sizes.keys() or True: # TODO - Disable resizing for now, but should revisit
            # Default resize to 50% if no sizes provided
            resize_image_height = int(rotated_image.shape[0] * image_scale)
            resize_image_width = int(rotated_image.shape[1] * image_scale)
        else:
            resize_image_height = int(display_image_sizes[camera_id]['height'])
            resize_image_width = int(display_image_sizes[camera_id]['width'])
        resized_img = cv2.resize(rotated_image, dsize=(resize_image_width, resize_image_height),
                                 interpolation=cv2.INTER_LINEAR) #TODO - see if other interpolation methods are faster/better
        _, jpeg_data = cv2.imencode('.jpg', resized_img, jpeg_encoding_parameters)
        jpeg_string = jpeg_data.tobytes()
        jpeg_string_length = len(jpeg_string)


        frame_height = resized_img.shape[0]
        frame_width = resized_img.shape[1]


        frame_header = np.array([(1,
                                  frame_number,
                                  camera_id.encode('utf-8'),
                                  frame_recarray.frame_metadata.camera_config.camera_index,
                                  frame_width,
                                  frame_height,
                                  frame_recarray.image.shape[2],
                                  jpeg_string_length)], dtype=FRONTEND_FRAME_HEADER_DTYPE)
        frame_header_bytes = frame_header.tobytes()

        # Ensure enough space in bytearray
        required_size = current_pos + len(frame_header_bytes) + jpeg_string_length
        if required_size > len(_reusable_bytes_payload):
            old_size = len(_reusable_bytes_payload)
            # resize the bytearray to accommodate the new data ([plus an additional 1MB for future frames])
            _reusable_bytes_payload.extend(bytearray((required_size - old_size) + ONE_MEGABYTE))
            logger.warning(
                f"Payload size ({old_size} bytes) exceeded pre-allocated size, resized to {len(_reusable_bytes_payload)} bytes")

        # Copy data into the reusable bytearray
        _reusable_bytes_payload[current_pos:current_pos + len(frame_header_bytes)] = frame_header_bytes
        current_pos += len(frame_header_bytes)
        _reusable_bytes_payload[current_pos:current_pos + jpeg_string_length] = jpeg_string
        current_pos += jpeg_string_length

    # Add footer
    payload_footer = np.array([(2, frame_number, number_of_cameras)],
                              dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    footer_bytes = payload_footer.tobytes()

    # Ensure enough space
    if current_pos + len(footer_bytes) > len(_reusable_bytes_payload):
        og_len = len(_reusable_bytes_payload)
        _reusable_bytes_payload.extend(bytearray(len(footer_bytes)))
        logging.warning(
            f"Payload size ({og_len}bytes) exceeded pre-allocated size, resized to {len(_reusable_bytes_payload)} bytes - change default pre-allocated size!")

    _reusable_bytes_payload[current_pos:current_pos + len(footer_bytes)] = footer_bytes
    current_pos += len(footer_bytes)

    frontend_bytes = _reusable_bytes_payload[:current_pos]
    return frame_number, np.mean(frame_timestamps), frontend_bytes
