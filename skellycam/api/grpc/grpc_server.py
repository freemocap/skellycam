import asyncio
import logging
import multiprocessing
import time
from concurrent import futures
from typing import AsyncGenerator, Dict, List, Optional

import cv2
import grpc
import numpy as np

from skellycam import LogLevels
from skellycam.api.grpc.grpc_generated import skellycam_pb2 as pb2
from skellycam.api.grpc.grpc_generated import skellycam_pb2_grpc as pb2_grpc
from skellycam.core.recorders.framerate_tracker import FramerateTracker
from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.skellycam_app.skellycam_app import get_skellycam_app, SkellycamApplication
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue, \
    LogRecordModel
from skellycam.utilities.wait_functions import async_wait_10ms

logger = logging.getLogger(__name__)



class SkellycamServicer(pb2_grpc.SkellycamServiceServicer):
    def __init__(self) -> None:
        self._app: SkellycamApplication = get_skellycam_app()
        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._websocket_queue: multiprocessing.Queue = get_websocket_log_queue()


    async def StreamMultiFrames(
            self,
            request: pb2.MultiFrameRequest,
            context: grpc.aio.ServicerContext
    ) -> AsyncGenerator[pb2.MultiFrameResponse, None]:
        """Stream camera frames to the client."""
        logger.info("Starting frame streaming")
        last_sent_frame_number: int = request.last_received_frame_number
        display_image_sizes: dict[str, dict[str, float]] = {
            camera_id: {"width": size.width, "height": size.height}
            for camera_id, size in request.display_image_sizes.items()
        }

        try:
            while context.is_active():
                # Get new multi-frames from the application
                new_multiframes = self._app.get_new_multiframes(
                    if_newer_than=last_sent_frame_number
                )

                for camera_group_id, mf_rec_array in new_multiframes.items():
                    # Create gRPC response directly from the multi-frame record array
                    response = self._create_multiframe_response(
                        camera_group_id,
                        mf_rec_array,
                        display_image_sizes
                    )

                    yield response
                    last_sent_frame_number = response.frame_number

                    # Update framerate tracker
                    if camera_group_id not in self._frontend_framerate_trackers:
                        self._frontend_framerate_trackers[camera_group_id] = self._app.create_framerate_tracker(
                            f"Frontend-{camera_group_id}"
                        )
                    self._frontend_framerate_trackers[camera_group_id].update(response.timestamp)

                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning

        except Exception as e:
            logger.exception(f"Error in frame streaming: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)

    def _create_multiframe_response(
            self,
            camera_group_id: str,
            mf_rec_array: np.recarray,
            display_image_sizes: dict[str, dict[str, float]] = None
    ) -> pb2.MultiFrameResponse:
        """Create a MultiFrameResponse from a multi-frame record array."""
        camera_ids = mf_rec_array.dtype.names
        frame_numbers = [mf_rec_array[camera_id].frame_metadata.frame_number[0] for camera_id in camera_ids]

        if len(set(frame_numbers)) != 1:
            raise ValueError("All cameras in the multi-frame record array must have the same frame number.")

        frame_number = frame_numbers[0]

        # Calculate average timestamp
        frame_timestamps = []
        for camera_id in camera_ids:
            frame_recarray = mf_rec_array[camera_id][0]
            frame_timestamps.append(np.mean([
                frame_recarray.frame_metadata.timestamps.pre_frame_grab_ns,
                frame_recarray.frame_metadata.timestamps.post_frame_grab_ns
            ]))

        multiframe_timestamp = np.mean(frame_timestamps)

        # Create camera frames
        camera_frames = []
        for camera_id in camera_ids:
            frame_recarray = mf_rec_array[camera_id][0]

            # Apply rotation if needed
            if frame_recarray.frame_metadata.camera_config.rotation != -1:
                rotated_image = cv2.rotate(
                    frame_recarray.image[:],
                    frame_recarray.frame_metadata.camera_config.rotation
                )
            else:
                rotated_image = frame_recarray.image[:]

            # Resize image
            image_scale = 0.5  # Default scale

            if (display_image_sizes is not None and
                    camera_id in display_image_sizes and
                    'width' in display_image_sizes[camera_id] and
                    'height' in display_image_sizes[camera_id]):

                resize_image_width = int(display_image_sizes[camera_id]['width'])
                resize_image_height = int(display_image_sizes[camera_id]['height'])
            else:
                resize_image_width = int(rotated_image.shape[1] * image_scale)
                resize_image_height = int(rotated_image.shape[0] * image_scale)

            resized_img = cv2.resize(
                rotated_image,
                dsize=(resize_image_width, resize_image_height),
                interpolation=cv2.INTER_LINEAR
            )

            # Compress to JPEG
            jpeg_encoding_parameters = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            _, jpeg_data = cv2.imencode('.jpg', resized_img, jpeg_encoding_parameters)

            # Create CameraFrameData
            camera_frame = pb2.CameraFrameData(
                camera_id=camera_id,
                camera_name=frame_recarray.frame_metadata.camera_config.name,  # Added camera_name
                camera_index=frame_recarray.frame_metadata.camera_config.camera_index,
                image_width=resize_image_width,
                image_height=resize_image_height,
                color_channels=resized_img.shape[2],
                jpeg_data=jpeg_data.tobytes()
            )

            camera_frames.append(camera_frame)

        # Create and return the response
        return pb2.MultiFrameResponse(
            frame_number=frame_number,
            camera_group_id=camera_group_id,
            timestamp=multiframe_timestamp,
            camera_frames=camera_frames
        )

    async def AcknowledgeMultiFrame(
            self,
            request: pb2.MultiFrameAcknowledgment,
            context: grpc.aio.ServicerContext
    ) -> pb2.AcknowledgmentResponse:
        """Handle frame acknowledgment from client."""
        try:
            # Update display image sizes if provided
            if request.display_image_sizes:
                display_image_sizes = {
                    camera_id: {"width": size.width, "height": size.height}
                    for camera_id, size in request.display_image_sizes.items()
                }
                # You might want to store these sizes for future use
                # or pass them to the application

            logger.debug(f"Received acknowledgment for frame {request.frame_number}")

            # Return success response
            return pb2.AcknowledgmentResponse(success=True)
        except Exception as e:
            logger.exception(f"Error processing frame acknowledgment: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb2.AcknowledgmentResponse(success=False)

    async def StreamLogs(
            self,
            request: pb2.LogRequest,
            context: grpc.aio.ServicerContext
    ) -> AsyncGenerator[pb2.LogRecord, None]:
        """Stream log messages to the client."""
        logger.info(f"Starting log streaming with minimum level: {request.min_level}")

        # Set the minimum log level for the handler
        min_level_map = {
            pb2.LogLevel.TRACE: LogLevels.TRACE,
            pb2.LogLevel.DEBUG: LogLevels.DEBUG,
            pb2.LogLevel.INFO: LogLevels.INFO,
            pb2.LogLevel.SUCCESS: LogLevels.SUCCESS,
            pb2.LogLevel.API: LogLevels.API,
            pb2.LogLevel.WARNING: LogLevels.WARNING,
            pb2.LogLevel.ERROR: LogLevels.ERROR,
            pb2.LogLevel.CRITICAL: LogLevels.CRITICAL,
        }

        min_level = min_level_map.get(request.min_level, logging.INFO)
        self._log_handler.setLevel(min_level)

        try:
            while context.is_active():
                try:

                    if not self._websocket_queue.empty():
                        log_record: LogRecordModel = LogRecordModel(**self._websocket_queue.get())
                        # Only yield records that meet the minimum level
                        if log_record.level_no >= min_level:
                            yield log_record
                    else:
                        await async_wait_10ms()

                except asyncio.TimeoutError:
                    # No log records available, continue waiting
                    continue

        except Exception as e:
            logger.exception(f"Error in log streaming: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)

    def _create_log_record_proto(self, record: LogRecordModel) -> pb2.LogRecord:
        """Convert a Python LogRecord to a protobuf LogRecord."""
        # Format the message

        # Get exception info if available
        exc_info = ""
        exc_text = ""
        if record.exc_info:
            exc_info = str(record.exc_info)
            if record.exc_text:
                exc_text = record.exc_text

        # Create and return the protobuf LogRecord
        return pb2.LogRecord(
            name=record.name,
            message=record.getMessage(),
            args=[str(arg) for arg in record.args] if record.args else [],
            level_name=record.levelname,
            level_no=record.levelno,
            pathname=record.pathname,
            filename=record.filename,
            module=record.module,
            exc_info=exc_info,
            exc_text=exc_text,
            stack_info=record.stack_info if record.stack_info else "",
            line_no=record.lineno,
            func_name=record.funcName,
            created=record.created,
            msecs=record.msecs,
            relative_created=record.relativeCreated,
            thread=record.thread,
            thread_name=record.threadName,
            process_name=record.processName if hasattr(record, 'processName') else "",
            process=record.process,
            delta_t=record.delta_t,
            formatted_message=record.formatted_message,
            asctime=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            type="log"
        )

    async def StreamFramerates(
            self,
            request: pb2.FramerateRequest,
            context: grpc.aio.ServicerContext
    ) -> AsyncGenerator[pb2.FramerateUpdate, None]:
        """Stream framerate updates to the client."""
        logger.info("Starting framerate streaming")

        # Filter by camera group ID if provided
        camera_group_id_filter = request.camera_group_id if request.camera_group_id else None

        try:
            while context.is_active():
                # Get all camera groups
                camera_groups = self._app.get_camera_groups()

                for camera_group_id, camera_group in camera_groups.items():
                    # Skip if filter is set and doesn't match
                    if camera_group_id_filter and camera_group_id != camera_group_id_filter:
                        continue

                    # Get backend framerate tracker
                    backend_tracker = camera_group.framerate_tracker

                    # Get frontend framerate tracker
                    frontend_tracker = self._frontend_framerate_trackers.get(camera_group_id)

                    # Create framerate update
                    update = pb2.FramerateUpdate(
                        camera_group_id=camera_group_id,
                        backend_framerate=self._create_framerate_data(backend_tracker) if backend_tracker else None,
                        frontend_framerate=self._create_framerate_data(frontend_tracker) if frontend_tracker else None
                    )

                    yield update

                # Wait before sending next update
                await asyncio.sleep(1.0)

        except Exception as e:
            logger.exception(f"Error in framerate streaming: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)

    def _create_framerate_data(self, tracker: FramerateTracker) -> pb2.FramerateData:
        """Create a FramerateData message from a FramerateTracker."""
        if not tracker:
            return None

        stats = tracker.get_stats()
        return pb2.FramerateData(
            mean_frame_duration_ms=stats.get('mean_frame_duration_ms', 0),
            mean_frames_per_second=stats.get('mean_frames_per_second', 0),
            frame_duration_min=stats.get('frame_duration_min', 0),
            frame_duration_max=stats.get('frame_duration_max', 0),
            frame_duration_stddev=stats.get('frame_duration_stddev', 0),
            frame_duration_median=stats.get('frame_duration_median', 0),
            frame_duration_coefficient_of_variation=stats.get('frame_duration_coefficient_of_variation', 0),
            calculation_window_size=tracker.window_size,
            framerate_source=tracker.name
        )


def serve_grpc(port: int = 50051) -> grpc.aio.Server:
    """Start the gRPC server."""
    server: grpc.aio.Server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_SkellycamServiceServicer_to_server(SkellycamServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    return server


async def start_grpc_server(port: int = 50051) -> None:
    """Start the gRPC server and keep it running."""
    server: grpc.aio.Server = serve_grpc(port)
    await server.start()
    logger.info(f"gRPC server started on port {port}")

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(0)