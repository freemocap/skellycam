import logging

from PySide6.QtCore import QObject, QTimer, Signal, QThread

logger = logging.getLogger(__name__)

from websockets.sync.client import connect


class WebsocketClient(QThread):
    # TODO - emit a MultiFramePayload object instead of a dict
    new_frames_received = Signal(dict)

    def __init__(
            self,
            hostname: str,
            port: int,
            parent: QObject,
    ):
        super().__init__(parent=parent)
        self.hostname = hostname
        self.port = port
        self.should_continue = True
        self.timer = QTimer(self)

    def run(self):
        logger.info("WebsocketClient starting...")
        ws_url = f"ws://{self.hostname}:{self.port}/ws"
        logger.info(f"Connecting to websocket server at: {ws_url}")
        with connect(ws_url) as websocket:
            while self.should_continue:
                message = websocket.recv()
                if isinstance(message, str):
                    self._handle_text_message(message)
                elif isinstance(message, bytes):
                    self._handle_binary_message(message)
                else:
                    logger.error(f"Received message of unexpected type: {type(message)}")

    def stop_requesting(self):
        logger.info("FrameGrabber stopping...")
        self.timer.stop()

    def _handle_binary_message(self, message: bytes):
        logger.debug(f"Received binary message {message} with size {len(message)} bytes.")

    def _handle_text_message(self, message: str):

        logger.debug(f"Received message: {message}")

        # if response:
        #     logger.trace(f"Received response: {response}")
        #     compressed_payload_str = response.json()
        #     if not compressed_payload_str:
        #         return
        #
        #     compressed_payload = json.loads(compressed_payload_str)
        #     new_frames = {}
        #     for camera_id, base64_image in compressed_payload.items():
        #         image_bytes = base64.b64decode(base64_image)
        #         image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        #         image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        #         new_frames[camera_id] = image
        #
        #     self.new_frames_received.emit(new_frames)
        #     logger.trace(
        #         f"Emitted new frames with images from cameras {new_frames.keys()}"
        #     )
        #
        # else:
        #     logger.trace("No frames received for this request.")
