# skellycam/api/udp/udp_server.py
import socket
import threading
import struct
import logging
import time
import numpy as np

from skellycam.skellycam_app.skellycam_app import get_skellycam_app
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt

logger = logging.getLogger(__name__)


class UDPServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.app = get_skellycam_app()
        self.running = False
        self.thread = None
        self.last_received_frontend_confirmation = -1
        self.last_sent_frame_number = -1
        self.display_image_sizes = None

    def start(self):
        """Start the UDP server in a separate thread"""
        self.socket.bind((self.host, self.port))
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        logger.info(f"UDP server started on {self.host}:{self.port}")

        # Start the frame sender thread
        self.sender_thread = threading.Thread(target=self._frame_sender, daemon=True)
        self.sender_thread.start()

    def _run_server(self):
        """Listen for incoming UDP messages (mainly acknowledgments)"""
        while self.running and self.app.should_continue:
            try:
                data, addr = self.socket.recvfrom(1024)
                self._handle_message(data, addr)
            except Exception as e:
                logger.error(f"Error in UDP server: {e}")

    def _handle_message(self, data, addr):
        """Handle incoming UDP messages"""
        try:
            # Parse message format: [message_type(1), frame_number(4), data...]
            message_type = data[0]

            if message_type == 1:  # Frame acknowledgment
                frame_number = struct.unpack('!I', data[1:5])[0]
                self.last_received_frontend_confirmation = frame_number

                # Extract display image sizes if included
                if len(data) > 5:
                    # Parse the JSON data for display sizes
                    # This would need proper implementation
                    pass

        except Exception as e:
            logger.error(f"Error handling UDP message: {e}")

    def _frame_sender(self):
        """Send frame metadata via UDP"""
        while self.running and self.app.should_continue:
            try:
                # Check if we should send new frames (based on backpressure)
                if self.last_received_frontend_confirmation >= self.last_sent_frame_number or self.last_sent_frame_number == -1:
                    # Get new frames from the app
                    new_frontend_payloads = self.app.get_new_frontend_payloads(
                        if_newer_than=self.last_sent_frame_number,
                        display_image_sizes=self.display_image_sizes
                    )

                    for camera_group_id, (frame_number, timestamp, _) in new_frontend_payloads.items():
                        # Instead of sending the full payload, just send metadata
                        # Format: [message_type(1), frame_number(4), timestamp(8), camera_group_id(variable)]
                        header = struct.pack('!BIQ', 2, frame_number, int(timestamp))
                        message = header + camera_group_id.encode('utf-8')

                        # Send to the client (would need to track client addresses)
                        # For now, assuming a single client at a predefined address
                        client_addr = ('localhost', 5556)  # Client port
                        self.socket.sendto(message, client_addr)

                        self.last_sent_frame_number = frame_number

            except Exception as e:
                logger.error(f"Error in frame sender: {e}")

            # Sleep briefly to avoid CPU spinning
            time.sleep(0.001)  # 1ms

    def stop(self):
        """Stop the UDP server"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.sender_thread:
            self.sender_thread.join(timeout=1.0)
        self.socket.close()
        logger.info("UDP server stopped")