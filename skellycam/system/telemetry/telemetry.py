"""
Telemetry integration for SkellyCam.

Initializes the skellypings TelemetryClient on startup and sends
an app_opened event with system specifications. Respects the user's
opt-in/opt-out choice stored in telemetry_config.json.
"""

import logging
import platform
from pathlib import Path

import psutil

import skellycam
from skellycam.system.default_paths import get_default_skellycam_base_folder_path
from skellycam.system.telemetry.telemetry_config import read_telemetry_enabled
from skellypings import TelemetryClient

logger = logging.getLogger(__name__)

SKELLYPINGS_SERVER_URL: str = "https://skellypings-401698866387.northamerica-northeast1.run.app"
SKELLYPINGS_SECRET: str = "b51d08425d492ebfcf5dd833da245fa8bff9ec54602bafea59ae6732d1c406c5"

_client: TelemetryClient | None = None


def _get_user_id_file() -> Path:
    return Path(get_default_skellycam_base_folder_path()) / "telemetry_uid"


def _collect_system_specs() -> dict[str, object]:
    """Collect anonymous system specifications."""
    mem = psutil.virtual_memory()
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(mem.total / (1024 ** 3), 1),
    }


def initialize_telemetry() -> None:
    """Start the telemetry client and send an app_opened event, if enabled."""
    global _client

    if not read_telemetry_enabled():
        logger.info("Telemetry is disabled by user preference")
        return

    _client = TelemetryClient(
        server_url=SKELLYPINGS_SERVER_URL,
        secret=SKELLYPINGS_SECRET,
        app_version=skellycam.__version__,
        user_id_file=_get_user_id_file(),
    )

    specs = _collect_system_specs()
    _client.track("app_opened", payload=specs)
    logger.info("Telemetry initialized (user_id=%s)", _client.user_id)


def shutdown_telemetry() -> None:
    """Flush remaining events and stop the telemetry client."""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None
        logger.info("Telemetry shut down")


def track_event(event_type: str, payload: dict[str, object] | None = None) -> None:
    """Track a telemetry event. No-op if telemetry is disabled."""
    if _client is not None:
        _client.track(event_type=event_type, payload=payload)
