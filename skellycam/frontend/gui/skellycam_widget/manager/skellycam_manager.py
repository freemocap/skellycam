import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QThread

from skellycam.backend.core.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.frontend.api_client.api_client import HttpClient
from skellycam.system.default_paths import create_default_recording_folder_path

logger = logging.getLogger(__name__)
from skellycam.frontend.gui.skellycam_widget.manager.helpers.websocket_client import (
    WebsocketClient,
)

if TYPE_CHECKING:
    from skellycam.frontend import SkellyCamWidget


class SkellyCamManager(QThread):
    def __init__(
        self,
        main_widget: "SkellyCamWidget",
        hostname: str,
        port: int,
    ):
        super().__init__()
        self.main_widget = main_widget
        self.http_client = HttpClient(hostname=hostname, port=port)
        self.ws_client = WebsocketClient(
            hostname=hostname,
            port=port,
            parent=self,
        )
        self.ws_client.start()
        self.connect_signals()

    def connect_signals(self) -> None:
        self.main_widget.welcome.start_session_button.clicked.connect(
            self.handle_start_session_button_clicked
        )

        self.main_widget.camera_parameter_tree.camera_configs_changed.connect(
            self.main_widget.camera_grid.update_camera_grid
        )

        self.ws_client.new_frames_received.connect(
            self.main_widget.camera_grid.handle_new_frames
        )

        self.main_widget.camera_control_buttons.close_cameras_button.clicked.connect(
            self._close_cameras
        )
        self.main_widget.camera_control_buttons.connect_to_cameras_button.clicked.connect(
            self._connect_to_cameras
        )

        self.main_widget.camera_control_buttons.detect_available_cameras_button.clicked.connect(
            self._detect_available_cameras
        )

        self.main_widget.camera_control_buttons.apply_camera_settings_button.clicked.connect(
            self._update_camera_configs
        )

        self.main_widget.record_buttons.start_recording_button.clicked.connect(
            self._start_recording
        )

        self.main_widget.record_buttons.stop_recording_button.clicked.connect(
            self._stop_recording
        )

    def handle_start_session_button_clicked(self):
        logger.debug("Start session button clicked!")
        self.main_widget.welcome.hide()
        self.main_widget.camera_grid.show()
        self.main_widget.record_buttons.show()
        self.main_widget.side_panel.show()

        self._detect_available_cameras()

    def _detect_available_cameras(self):
        logger.debug("Sending detect available cameras request...")

        detected_cameras_response = self.http_client.detect_available_cameras()

        self.handle_cameras_detected(
            detected_cameras_response, link_connect_to_cameras=True
        )

    def _connect_to_cameras(self):
        logger.info("Sending connect to cameras request...")

        connect_to_cameras_response = self.http_client.connect_to_cameras(
            camera_configs=self.main_widget.camera_parameter_tree.camera_configs
        )

        if connect_to_cameras_response and connect_to_cameras_response.success:
            self.handle_cameras_connected()
        else:
            logger.error("Failed to connect to cameras")

    def _update_camera_configs(self):
        logger.info("Sending update camera configs request...")

        camera_configs = self.main_widget.camera_parameter_tree.camera_configs
        update_camera_configs_response = self.http_client.update_camera_configs(
            camera_configs
        )

        logger.info(f"Update camera configs response: {update_camera_configs_response}")

    def _close_cameras(self):
        logger.info("Sending close cameras request...")

        close_cameras_response = self.http_client.close_cameras()

        self._handle_cameras_closed_response()

    def _start_recording(self):
        logger.info("Sending start recording request...")

        start_recording_response = self.http_client.start_recording(
            recording_folder_path=create_default_recording_folder_path()
        )

        logger.info(f"Start recording response: {start_recording_response}")
        self._handle_start_recording()

    def _stop_recording(self):
        logger.info("Sending stop recording request...")

        stop_recording_response = self.http_client.stop_recording()

        self._handle_stop_recording_response()

    def handle_cameras_connected(self):
        logger.info("Handling cameras connected signal")
        self.main_widget.camera_control_buttons.close_cameras_button.setEnabled(True)
        self.main_widget.camera_control_buttons.apply_camera_settings_button.setEnabled(
            True
        )
        self.main_widget.record_buttons.start_recording_button.setEnabled(True)
        self.main_widget.record_buttons.start_recording_button.setFocus()
        self.ws_client.start()

    def handle_cameras_detected(
        self,
        detected_cameras_response: CamerasDetectedResponse,
        link_connect_to_cameras: bool,
    ) -> None:
        logger.debug("Handling `cameras detected`...")

        self.main_widget.camera_parameter_tree.update_available_cameras(
            available_cameras=detected_cameras_response.detected_cameras
        )

        self.main_widget.camera_control_buttons.detect_available_cameras_button.setEnabled(
            True
        )
        self.main_widget.camera_control_buttons.connect_to_cameras_button.setEnabled(
            True
        )

        if (
            not detected_cameras_response
            or len(detected_cameras_response.detected_cameras.keys()) == 0
        ):
            logger.warning("No core detected!")
            self.main_widget.camera_control_buttons.detect_available_cameras_button.setFocus()
            return

        self.main_widget.camera_control_buttons.connect_to_cameras_button.setFocus()

        if link_connect_to_cameras:
            logger.debug("Linking `connect to core` request...")
            self._connect_to_cameras()

    def _handle_cameras_closed_response(self):
        logger.debug("Handling core closed response")
        self.main_widget.camera_control_buttons.close_cameras_button.setEnabled(False)
        self.main_widget.camera_control_buttons.connect_to_cameras_button.hasFocus()
        self.main_widget.record_buttons.start_recording_button.setEnabled(False)

    def _handle_stop_recording_response(self):
        logger.debug("Handling stop recording response")
        self.main_widget.record_buttons.start_recording_button.setEnabled(True)
        self.main_widget.record_buttons.stop_recording_button.setEnabled(False)

    def _handle_start_recording(self):
        logger.debug("Handling start recording response")
        self.main_widget.record_buttons.start_recording_button.setEnabled(False)
        self.main_widget.record_buttons.stop_recording_button.setEnabled(True)
        self.main_widget.record_buttons.stop_recording_button.setFocus()
