# skellycam/api/zeromq/zeromq_server.py
import logging
import time
import zmq
import threading
import json

from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt, MultiframeTimestampFloat
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, get_skellycam_app

logger = logging.getLogger(__name__)


class ZeroMQServer:
    def __init__(self, pub_port=5555, sub_port=5556):
        self.pub_port = pub_port
        self.sub_port = sub_port
        self._app: SkellycamApplication = get_skellycam_app()
        self._should_continue = True
        self.last_sent_frame_number = -1
        self._display_image_sizes = None
        self.context = None
        self.pub_socket = None
        self.sub_socket = None
        self.pub_thread = None
        self.sub_thread = None

    def start(self):
        """Start the ZeroMQ server in separate threads"""
        logger.info(f"Starting ZeroMQ server (PUB on port {self.pub_port}, SUB on port {self.sub_port})...")

        # Initialize ZeroMQ context
        self.context = zmq.Context()

        # Start publisher thread for sending images
        self.pub_thread = threading.Thread(target=self._run_publisher, daemon=True)
        self.pub_thread.start()

        # Start subscriber thread for receiving acknowledgments
        self.sub_thread = threading.Thread(target=self._run_subscriber, daemon=True)
        self.sub_thread.start()

        return self

    def stop(self):
        """Stop the ZeroMQ server"""
        logger.info("Stopping ZeroMQ server...")
        self._should_continue = False

        # Wait for threads to finish
        if self.pub_thread:
            self.pub_thread.join(timeout=1.0)
        if self.sub_thread:
            self.sub_thread.join(timeout=1.0)

        # Close sockets
        if self.pub_socket:
            self.pub_socket.close()
        if self.sub_socket:
            self.sub_socket.close()

        # Terminate context
        if self.context:
            self.context.term()

        logger.info("ZeroMQ server stopped.")

    def _run_publisher(self):
        """Run the ZeroMQ publisher for sending images"""
        try:
            # Initialize publisher socket
            self.pub_socket = self.context.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://*:{self.pub_port}")

            # Give the socket time to initialize
            time.sleep(0.1)

            logger.info(f"ZeroMQ publisher running on port {self.pub_port}")

            while self._should_continue and self._app.should_continue:
                # Get new frames from the app
                new_frontend_payloads: dict[
                    CameraGroupIdString, tuple[
                        FrameNumberInt, MultiframeTimestampFloat, bytes]] = self._app.get_new_frontend_payloads(
                    if_newer_than=self.last_sent_frame_number,
                    display_image_sizes=self._display_image_sizes)

                # Send each frame over ZeroMQ
                for camera_group_id, (frame_number, multiframe_timestamp,
                                      payload_bytes) in new_frontend_payloads.items():
                    # Send the frame with a topic (camera_group_id)
                    self.pub_socket.send_multipart([
                        camera_group_id.encode('utf-8'),  # Topic
                        frame_number.to_bytes(8, byteorder='little'),  # Frame number
                        payload_bytes  # Image payload
                    ])
                    self.last_sent_frame_number = frame_number

                # Small sleep to avoid CPU spinning
                time.sleep(0.01)

        except Exception as e:
            logger.exception(f"Error in ZeroMQ publisher: {e.__class__}: {e}")
            get_skellycam_app().kill_everything()
            raise
        finally:
            if self.pub_socket:
                self.pub_socket.close()
            logger.info("ZeroMQ publisher thread exited.")

    def _run_subscriber(self):
        """Run the ZeroMQ subscriber for receiving acknowledgments"""
        try:
            # Initialize subscriber socket
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.bind(f"tcp://*:{self.sub_port}")
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "ack")

            logger.info(f"ZeroMQ subscriber running on port {self.sub_port}")

            # Set up poller for non-blocking receive
            poller = zmq.Poller()
            poller.register(self.sub_socket, zmq.POLLIN)

            while self._should_continue and self._app.should_continue:
                # Poll for messages with timeout
                socks = dict(poller.poll(100))  # 100ms timeout

                if self.sub_socket in socks and socks[self.sub_socket] == zmq.POLLIN:
                    # Receive acknowledgment
                    topic, ack_data = self.sub_socket.recv_multipart()

                    try:
                        # Parse acknowledgment data
                        ack = json.loads(ack_data.decode('utf-8'))

                        # Update display image sizes
                        if 'frameNumber' in ack and 'displayImageSizes' in ack:
                            self._display_image_sizes = ack['displayImageSizes']
                            logger.debug(f"Received frame acknowledgment for frame {ack['frameNumber']}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode acknowledgment JSON: {ack_data}")

                # Small sleep to avoid CPU spinning
                time.sleep(0.01)

        except Exception as e:
            logger.exception(f"Error in ZeroMQ subscriber: {e.__class__}: {e}")
            get_skellycam_app().kill_everything()
            raise
        finally:
            if self.sub_socket:
                self.sub_socket.close()
            logger.info("ZeroMQ subscriber thread exited.")