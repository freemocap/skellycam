import multiprocessing
from typing import TYPE_CHECKING, Dict

from skellycam.backend.controller.interactions.base_models import BaseResponse
from skellycam.backend.controller.interactions.close_cameras import CloseCamerasInteraction, CloseCamerasResponse
from skellycam.backend.controller.interactions.connect_to_cameras import ConnectToCamerasInteraction, \
    ConnectToCamerasResponse
from skellycam.backend.controller.interactions.detect_available_cameras import CamerasDetectedResponse, \
    DetectAvailableCamerasInteraction
from skellycam.backend.controller.interactions.start_recording_interaction import StartRecordingInteraction
from skellycam.backend.controller.interactions.stop_recording_interaction import StopRecordingInteraction, \
    StopRecordingResponse
from skellycam.backend.controller.interactions.update_camera_configs import UpdateCameraConfigsInteraction
from skellycam.frontend.gui.skellycam_widget.helpers.backend_communicator import BackendCommunicator
from skellycam.frontend.manager.helpers.frame_grabber import FrameGrabber
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.system.environment.get_logger import logger

if TYPE_CHECKING:
    from skellycam.frontend.gui.skellycam_widget.skellycam_widget import SkellyCamWidget
    from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.camera_views.camera_grid import CameraGrid
    from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.record_buttons import RecordButtons
    from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.welcome import Welcome
    from skellycam.frontend.gui.skellycam_widget.sub_widgets.side_panel_widgets.camera_control_buttons import \
        CameraControlButtons
    from skellycam.frontend.gui.skellycam_widget.sub_widgets.side_panel_widgets.camera_parameter_tree import \
        CameraParameterTree


class SkellycamManager:
    def __init__(self,
                 main_widget: 'SkellyCamWidget',
                 exit_event: multiprocessing.Event,
                 messages_from_frontend: multiprocessing.Queue = None,
                 messages_from_backend: multiprocessing.Queue = None,
                 frontend_frame_pipe_receiver=None,  # multiprocessing.connection.Connection
                 ) -> None:

        self._exit_event = exit_event

        if any([messages_from_frontend is None,
                messages_from_backend is None,
                frontend_frame_pipe_receiver is None]):

            if not all([messages_from_frontend is None,
                        messages_from_backend is None,
                        frontend_frame_pipe_receiver is None]):
                raise ValueError("If any of the backend communication objects are None, all must be None")
            self._start_backend_and_frontend_processes()
            logger.info("Running in Widget-mode, spawning backend processes")
        else:
            self._messages_from_frontend = messages_from_frontend
            self._messages_from_backend = messages_from_backend
            self._frontend_frame_pipe_receiver = frontend_frame_pipe_receiver

        self.main_widget = main_widget

        self._backend_communicator = BackendCommunicator(messages_from_frontend=self._messages_from_frontend,
                                                         messages_from_backend=self._messages_from_backend,
                                                         frontend_frame_pipe_receiver=self._frontend_frame_pipe_receiver,
                                                         handle_backend_response=self.handle_backend_response,
                                                         parent=self.main_widget)
        self._frame_grabber = FrameGrabber(parent=self.main_widget,
                                           frontend_frame_pipe_receiver=self._frontend_frame_pipe_receiver)

        self._frame_grabber.start()
        self._backend_communicator.start()

        self._connect_signals()

    def _start_backend_and_frontend_processes(self):
        from skellycam._main.helpers import create_queues_and_pipes, start_backend_process

        (self._frontend_frame_pipe_receiver,
         self._frontend_frame_pipe_sender,
         self._messages_from_backend,
         self._messages_from_frontend) = create_queues_and_pipes()

        self._backend_process = start_backend_process(exit_event=self._exit_event,
                                                      messages_from_frontend=self._messages_from_frontend,
                                                      messages_from_backend=self._messages_from_backend,
                                                      frontend_frame_pipe_sender=self._frontend_frame_pipe_sender)

    # Main Backend Response Handler
    def handle_backend_response(self, response: BaseResponse) -> None:
        logger.debug(f"Handling Backend response: {response}")

        if isinstance(response, CamerasDetectedResponse):
            self._handle_cameras_detected_response(response)
        elif isinstance(response, ConnectToCamerasResponse):
            self._handle_cameras_connected_response()
        elif isinstance(response, CloseCamerasResponse):
            self._handle_cameras_closed_response()
        elif isinstance(response, StopRecordingResponse):
            self._handle_stop_recording_response()
        elif isinstance(response, BaseResponse):
            logger.debug(f"Received BaseResponse with no defined 'response' behavior: {response}")
        else:
            raise ValueError(f"Unknown response type: {response}")

    @property
    def welcome(self) -> 'Welcome':
        return self.main_widget.welcome

    @property
    def camera_grid(self) -> 'CameraGrid':
        return self.main_widget.camera_grid

    @property
    def record_buttons(self) -> 'RecordButtons':
        return self.main_widget.record_buttons

    @property
    def camera_parameter_tree(self) -> 'CameraParameterTree':
        return self.main_widget.camera_parameter_tree

    @property
    def camera_control_buttons(self) -> 'CameraControlButtons':
        return self.main_widget.camera_control_buttons

    @property
    def camera_configs(self) -> Dict[CameraId, CameraConfig]:
        return self.camera_parameter_tree.camera_configs

    def _connect_signals(self) -> None:

        self.welcome.start_session_button.clicked.connect(self._handle_start_session_signal)

        self._frame_grabber.new_frames.connect(self.camera_grid.handle_new_images)

        self.record_buttons.start_recording_button.clicked.connect(
            lambda: self._backend_communicator.send_interaction_to_backend(StartRecordingInteraction.as_request()))

        self.record_buttons.stop_recording_button.clicked.connect(
            lambda: self._backend_communicator.send_interaction_to_backend(StopRecordingInteraction.as_request())
        )

        self.camera_control_buttons.close_cameras_button.clicked.connect(
            lambda: self._backend_communicator.send_interaction_to_backend(CloseCamerasInteraction.as_request()))

        self.camera_control_buttons.connect_to_cameras_button.clicked.connect(
            lambda: self._backend_communicator.send_interaction_to_backend(
                ConnectToCamerasInteraction.as_request(camera_configs=self.camera_configs)))

        self.camera_control_buttons.detect_available_cameras_button.clicked.connect(
            lambda: self._backend_communicator.send_interaction_to_backend(
                DetectAvailableCamerasInteraction.as_request()))

        self.camera_control_buttons.apply_camera_settings_button.clicked.connect(
            lambda: self._backend_communicator.send_interaction_to_backend(
                UpdateCameraConfigsInteraction.as_request(camera_configs=self.camera_configs)))

    def _handle_start_session_signal(self):
        self.main_widget.welcome.hide()
        self.main_widget.camera_grid.show()
        self.main_widget.record_buttons.show()
        self.main_widget.side_panel.show()

        self._backend_communicator.send_interaction_to_backend(
            DetectAvailableCamerasInteraction.as_request())

    def _handle_cameras_detected_response(self, response: CamerasDetectedResponse):
        logger.debug(f"Handling cameras detected response: {response}")
        self.camera_parameter_tree.update_available_cameras(available_cameras=response.available_cameras)
        self.camera_grid.update_camera_grid(camera_configs=self.camera_configs)
        self.camera_control_buttons.detect_available_cameras_button.setEnabled(True)
        self.camera_control_buttons.connect_to_cameras_button.setEnabled(True)
        self.camera_control_buttons.connect_to_cameras_button.setFocus()

        self._backend_communicator.send_interaction_to_backend(
            ConnectToCamerasInteraction.as_request(camera_configs=self.camera_configs))

    def _handle_cameras_connected_response(self):
        self.camera_control_buttons.close_cameras_button.setEnabled(True)
        self.camera_control_buttons.apply_camera_settings_button.setEnabled(True)
        self.record_buttons.start_recording_button.setEnabled(True)
        self.record_buttons.start_recording_button.setFocus()

    def _handle_cameras_closed_response(self):
        self.camera_control_buttons.close_cameras_button.setEnabled(False)
        self.camera_control_buttons.connect_to_cameras_button.hasFocus()
        self.record_buttons.start_recording_button.setEnabled(False)

    def _handle_stop_recording_response(self):
        self.record_buttons.start_recording_button.setEnabled(True)
        self.record_buttons.stop_recording_button.setEnabled(False)
