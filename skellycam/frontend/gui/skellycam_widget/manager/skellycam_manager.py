from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, QThread

from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    DetectedCameras,
    CamerasDetectedResponse,
)
from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.gui.skellycam_widget.manager.helpers.frame_requester import (
    FrameRequester,
)

if TYPE_CHECKING:
    from skellycam.frontend import SkellyCamWidget


class SkellyCamManager(QThread):
    cameras_detected = Signal(DetectedCameras)

    def __init__(
        self,
        main_widget: "SkellyCamWidget",
    ):
        super().__init__()
        self.main_widget = main_widget
        self.api_client = self.main_widget.api_client
        self.frame_requester = FrameRequester(
            websocket_connection=self.api_client.websocket_connection, parent=self
        )
        self.connect_signals()

    def connect_signals(self) -> None:
        self.main_widget.welcome.start_session_button.clicked.connect(
            self.handle_start_session_button_clicked
        )

        self.main_widget.camera_parameter_tree.camera_configs_changed.connect(
            self.main_widget.camera_grid.update_camera_grid
        )

        self.api_client.websocket_connection.frames_received.connect(
            self.main_widget.camera_grid.handle_new_frames
        )

        self.api_client.detected_cameras.connect(self.handle_cameras_detected)
        self.api_client.cameras_connected.connect(self.handle_cameras_connected)

        #
        # self.main_widget.record_buttons.start_recording_button.clicked.connect(
        #     lambda: self.main_widget._backend_communicator.send_interaction_to_backend(
        #         StartRecordingInteraction.as_request()
        #     )
        # )
        #
        # self.main_widget.record_buttons.stop_recording_button.clicked.connect(
        #     lambda: self.main_widget._backend_communicator.send_interaction_to_backend(
        #         StopRecordingInteraction.as_request()
        #     )
        # )
        #
        # self.main_widget.camera_control_buttons.close_cameras_button.clicked.connect(
        #     lambda: self.main_widget._backend_communicator.send_interaction_to_backend(
        #         CloseCamerasInteraction.as_request()
        #     )
        # )
        #
        # self.main_widget.camera_control_buttons.connect_to_cameras_button.clicked.connect(
        #     lambda: self.main_widget._backend_communicator.send_interaction_to_backend(
        #         ConnectToCamerasInteraction.as_request(
        #             camera_configs=self.main_widget.camera_configs
        #         )
        #     )
        # )
        #
        # self.main_widget.camera_control_buttons.detect_available_cameras_button.clicked.connect(
        #     lambda: self.main_widget._backend_communicator.send_interaction_to_backend(
        #         DetectAvailableCamerasInteraction.as_request()
        #     )
        # )
        #
        # self.main_widget.camera_control_buttons.apply_camera_settings_button.clicked.connect(
        #     lambda: self.main_widget._backend_communicator.send_interaction_to_backend(
        #         UpdateCameraConfigsInteraction.as_request(
        #             camera_configs=self.main_widget.camera_configs
        #         )
        #     )
        # )

    def handle_start_session_button_clicked(self):
        logger.debug("Start session button clicked!")
        self.main_widget.welcome.hide()
        self.main_widget.camera_grid.show()
        self.main_widget.record_buttons.show()
        self.main_widget.side_panel.show()

        self.api_client.detect_available_cameras()
        self._request_connect_to_cameras()

    def _request_connect_to_cameras(self):
        logger.info("Sending connect to cameras request...")
        self.api_client.connect_to_cameras(
            self.main_widget.camera_parameter_tree.camera_configs
        )
        self.frame_requester.start()
        # self.handle_cameras_connected()

    def handle_cameras_detected(
        self, detected_cameras_response: CamerasDetectedResponse
    ) -> None:
        self.main_widget.camera_parameter_tree.update_available_cameras(
            available_cameras=detected_cameras_response.detected_cameras
        )

        self.main_widget.camera_control_buttons.detect_available_cameras_button.setEnabled(
            True
        )
        self.main_widget.camera_control_buttons.connect_to_cameras_button.setEnabled(
            True
        )
        self.main_widget.camera_control_buttons.connect_to_cameras_button.setFocus()

    def handle_cameras_connected(self):
        logger.info("Handling cameras connected signal")
        self.main_widget.camera_control_buttons.close_cameras_button.setEnabled(True)
        self.main_widget.camera_control_buttons.apply_camera_settings_button.setEnabled(
            True
        )
        self.main_widget.record_buttons.start_recording_button.setEnabled(True)
        self.main_widget.record_buttons.start_recording_button.setFocus()

    # def _handle_cameras_closed_response(self)):
    #     main_widget.camera_control_buttons.close_cameras_button.setEnabled(False)
    #     main_widget.camera_control_buttons.connect_to_cameras_button.hasFocus()
    #     main_widget.record_buttons.start_recording_button.setEnabled(False)
    #
    #
    # def _handle_stop_recording_response(self)):
    #     main_widget.record_buttons.start_recording_button.setEnabled(True)
    #     main_widget.record_buttons.stop_recording_button.setEnabled(False)
