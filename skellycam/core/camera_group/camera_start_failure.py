"""Explain a failed camera start: what was requested, what happened, why, and what to try.

Both camera backends fail through CameraBackendManager, so the explanation is composed once, after the
failure, from facts available then: the requested settings, a fresh camera detection (each camera's USB
connection, and requested cameras that are no longer detected) and, on Windows, the USB devices the
system reported surprise-removed during the start (Kernel-PnP event 1010, "surprise removed as it is
reported as missing on the bus").
"""
import logging
import platform
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

NO_FRAMES = ("waiting for frames", "read initial frame", "no frames")
CANNOT_OPEN = ("failed to open", "not connected", "cap_openstreamraw returned", "could not open", "not found")


def usb_disconnects_since(start: datetime) -> int | None:
    """USB devices Windows reported surprise-removed since `start`; None where this is not available."""
    if platform.system() != "Windows":
        return None
    since = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    query = f"*[System[(EventID=1010) and TimeCreated[@SystemTime>='{since}']]]"
    try:
        result = subprocess.run(["wevtutil", "qe", "Microsoft-Windows-Kernel-PnP/Device Management",
                                 f"/q:{query}", "/f:xml"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.count("<Event ") if result.returncode == 0 else None


def explain_start_failure(error: BaseException, configs: dict, detected: list | None,
                          usb_disconnects: int | None) -> str:
    """`detected`: CameraDeviceInfo from a detection after the failure (None if detection failed)."""
    connections = {camera.camera_id: camera.usb_version for camera in detected or []}
    requested_ids = [camera_id for camera_id, config in configs.items() if config.use_this_camera]
    requested = []
    for camera_id in requested_ids:
        config = configs[camera_id]
        rate = f"{config.framerate:g} fps" if config.framerate > 0 else "the camera's default frame rate"
        connection = connections.get(camera_id) or "USB connection unknown"
        requested.append(f"{camera_id} ({connection}): {config.capture_fourcc} "
                         f"{config.resolution.width}×{config.resolution.height} at {rate}")
    # Camera IDs come from detection; when none of them match, they are not detection IDs (or every
    # camera vanished, which an empty detection shows).
    compare = detected is not None and (not detected or any(camera_id in connections for camera_id in requested_ids))
    missing = [camera_id for camera_id in requested_ids if compare and camera_id not in connections]

    happened = [str(error).rstrip(". ") + "."]
    if usb_disconnects:
        happened.append(f"Windows reported {usb_disconnects} USB device disconnection(s) during the start.")
    if missing:
        happened.append(f"Not detected after the failure: {', '.join(missing)}.")

    message = str(error).lower()
    if usb_disconnects or missing:
        why = ("USB devices disconnecting while cameras start means the USB controller reset. That happens when "
               "the cameras together request more data than the USB connection can carry. The data each camera "
               "needs grows with resolution and frame rate, and a USB 2 connection carries far less than USB 3.")
        advice = ("Lower the frame rate or resolution, connect fewer cameras to the same USB controller, or move "
                  "cameras to ports on another USB controller. Detect cameras again before reconnecting.")
    elif any(marker in message for marker in NO_FRAMES):
        why = ("A camera that opens but sends no frames is usually in use by another program, or its USB "
               "connection cannot carry the requested resolution and frame rate.")
        advice = "Close other programs that use the camera. If none do, lower the frame rate or resolution."
    elif any(marker in message for marker in CANNOT_OPEN):
        why = "The camera could not be opened. It may be in use by another program, unplugged, or still reconnecting."
        advice = "Close other programs that use the camera, check its cable, and detect cameras again."
    else:
        why = "The camera backend reported the error above while starting the cameras."
        advice = ("Detect cameras again and retry. If it happens again, lower the frame rate or resolution, "
                  "or try the other camera backend.")
    return "\n".join([
        f"Could not start {len(requested)} camera(s) with these settings.",
        "Requested: " + "; ".join(requested) + ".",
        "What happened: " + " ".join(happened),
        "Why: " + why,
        "What to try: " + advice,
    ])


def describe_start_failure(error: BaseException, configs: dict, started: datetime) -> str:
    """Gather the post-failure facts and explain. Never raises: the original error stays attached."""
    try:
        from skellycam.core.device_detection.detect_cameras_devices import detect_available_cameras
        detected = detect_available_cameras()
    except Exception as detection_error:
        logger.warning(f"Camera detection after a failed start also failed: {detection_error}")
        detected = None
    return explain_start_failure(error, configs, detected, usb_disconnects_since(started))
