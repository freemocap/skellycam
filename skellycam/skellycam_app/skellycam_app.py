
import logging
import multiprocessing
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import (
    CameraGroupIdString,
    FrameNumberInt,
    CameraIdString,
    MultiframeTimestampFloat
)

logger = logging.getLogger(__name__)


@dataclass
class SkellycamApplication:
    """
    Main application class for SkellyCam.
    Manages camera groups and coordinates system-wide operations.
    """

    global_kill_flag: multiprocessing.Value
    camera_group_manager: CameraGroupManager = field(init=False)

    def __post_init__(self) -> None:
        """Initialize components after dataclass initialization."""
        self.camera_group_manager = CameraGroupManager(
            global_kill_flag=self.global_kill_flag
        )

    @classmethod
    def initialize(
            cls,
            global_kill_flag: multiprocessing.Value
    ) -> 'SkellycamApplication':
        """
        Factory method to create a new SkellyCam application instance.

        Args:
            global_kill_flag: Shared flag for coordinated shutdown

        Returns:
            Initialized SkellyCam application
        """
        logger.info("Initializing SkellyCam application")
        return cls(global_kill_flag=global_kill_flag)

    @property
    def should_continue(self) -> bool:
        """Check if the application should continue running."""
        return not self.global_kill_flag.value

    # Camera Group Management

    def create_camera_group(
            self,
            camera_configs: CameraConfigs
    ) ->CameraGroup|None:
        """
        Create or update a camera group with the given configurations.

        Args:
            camera_configs: Dictionary of camera configurations

        Returns:
            Created or updated camera group, or None if failed
        """
        camera_ids = list(camera_configs.keys())

        # Check if group already exists
        existing_group = self.camera_group_manager.find_camera_group_by_camera_ids(
            camera_ids=camera_ids
        )

        if existing_group:
            logger.info(
                f"Updating existing camera group {existing_group.id} "
                f"with cameras: {camera_ids}"
            )
            self.camera_group_manager.update_camera_settings(
                camera_configs=camera_configs
            )
            return existing_group

        # Create new group
        logger.info(f"Creating new camera group with cameras: {camera_ids}")
        camera_group = self.camera_group_manager.create_and_start_camera_group(
            camera_configs=camera_configs
        )

        if camera_group is None:
            logger.error("Failed to create camera group")
            return None

        logger.info(
            f"Camera group created with ID: {camera_group.id} "
            f"and cameras: {camera_ids}"
        )
        return camera_group

    def update_camera_configs(
            self,
            camera_configs: CameraConfigs
    ) -> CameraConfigs:
        """Update camera configurations."""
        return self.camera_group_manager.update_camera_settings(
            camera_configs=camera_configs
        )

    def get_new_frontend_payloads(
            self,
            if_newer_than: int,
            display_image_sizes: dict[CameraIdString, dict[str, float]]
    ) -> dict[CameraGroupIdString, tuple[FrameNumberInt, MultiframeTimestampFloat, bytes]]:
        """Get latest frontend payloads for display."""
        return self.camera_group_manager.get_latest_frontend_payloads(
            if_newer_than=if_newer_than,
            display_image_sizes=display_image_sizes
        )

    # Recording Control

    def start_recording(self, recording_info: RecordingInfo) -> None:
        """Start recording on all camera groups."""
        logger.info("Starting recording on all camera groups")
        self.camera_group_manager.start_recording_all_groups(
            recording_info=recording_info
        )

    def stop_recording(self) -> None:
        """Stop recording on all camera groups."""
        logger.info("Stopping recording on all camera groups")
        self.camera_group_manager.stop_recording_all_groups()

    # Playback Control

    def pause_camera_groups(self) -> None:
        """Pause all camera groups."""
        self.camera_group_manager.pause_all_groups()
        logger.info("All camera groups paused")

    def unpause_camera_groups(self) -> None:
        """Unpause all camera groups."""
        self.camera_group_manager.unpause_all_groups()
        logger.info("All camera groups unpaused")

    def toggle_pause_camera_groups(self) -> None:
        """Toggle pause state for all camera groups."""
        self.camera_group_manager.pause_unpause_all_groups()
        logger.info("Toggled pause state for all camera groups")

    # Lifecycle Management

    def shutdown(self) -> None:
        """
        Perform graceful shutdown of the application.
        Closes all camera groups and sets kill flag.
        """
        logger.info("Shutting down SkellyCam application")

        # Set kill flag first to notify all components
        self.global_kill_flag.value = True

        # Close all camera groups
        self.camera_group_manager.close_all_camera_groups()

        logger.success("SkellyCam application shutdown complete")

    def emergency_shutdown(self) -> None:
        """Emergency shutdown for critical failures."""
        logger.critical("EMERGENCY SHUTDOWN initiated!")
        self.shutdown()

    # State Export

    def get_state_dto(self) -> 'SkellycamAppStateDTO':
        """Get serializable state representation."""
        return SkellycamAppStateDTO.from_application(self)


class SkellycamAppStateDTO(BaseModel):
    """
    Data Transfer Object for SkellyCam application state.
    Used for API responses and state serialization.
    """

    type: str = "SkellycamAppStateDTO"
    state_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    camera_configs:CameraConfigs|None = None
    is_recording: bool = False
    camera_group_count: int = 0

    @classmethod
    def from_application(cls, app: SkellycamApplication) -> 'SkellycamAppStateDTO':
        """
        Create DTO from application instance.

        Args:
            app: SkellyCam application instance

        Returns:
            State DTO
        """
        # Get first camera group's configs if available
        camera_configs = None
        camera_groups = app.camera_group_manager.get_all_camera_groups()
        if camera_groups:
            camera_configs = camera_groups[0].camera_configs

        return cls(
            camera_configs=camera_configs,
            is_recording=app.camera_group_manager.is_recording,
            camera_group_count=len(camera_groups)
        )


# Singleton Management (if needed for backwards compatibility)

_SKELLYCAM_APP:SkellycamApplication|None = None


def get_skellycam_app() -> SkellycamApplication:
    """
    Get the singleton SkellyCam application instance.

    Returns:
        SkellyCam application instance

    Raises:
        RuntimeError: If application not initialized
    """
    if _SKELLYCAM_APP is None:
        raise RuntimeError(
            "SkellyCam application not initialized. "
            "Call create_skellycam_app() first."
        )
    return _SKELLYCAM_APP


def create_skellycam_app(
        global_kill_flag: multiprocessing.Value
) -> SkellycamApplication:
    """
    Create the singleton SkellyCam application instance.

    Args:
        global_kill_flag: Shared flag for coordinated shutdown

    Returns:
        Created SkellyCam application instance

    Raises:
        RuntimeError: If application already exists
    """
    global _SKELLYCAM_APP

    if _SKELLYCAM_APP is not None:
        raise RuntimeError("SkellyCam application already exists")

    _SKELLYCAM_APP = SkellycamApplication.initialize(
        global_kill_flag=global_kill_flag
    )
    return _SKELLYCAM_APP