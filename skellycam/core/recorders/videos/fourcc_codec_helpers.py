import logging
import os
import signal
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Sentinel value returned by resolve_writer_fourcc when OpenCV H264 is
# unavailable but pyav/libx264 is. VideoRecorder detects this and uses
# _PyavVideoWriter instead of cv2.VideoWriter.
PYAV_H264_FOURCC = 'X264_PYAV'

# OpenCV codecs that are also playable in Chromium/Electron (tried first).
#   X264/H264 — compact H.264 mp4. Bundled on Windows OpenCV; usually NOT on
#               pip-installed OpenCV for Linux/macOS (no libx264).
#   avc1      — H.264 via Apple VideoToolbox. Mac-native MP4 path.
WEB_COMPATIBLE_CODECS = ["X264", "H264", "avc1", PYAV_H264_FOURCC]

# Codecs that OpenCV can write but Chromium cannot play (last resort only).
#   mp4v      — MPEG-4 Part 2, removed from Chrome for licensing reasons. 
#               Less efficient than H.264 but very widely available, including on macOS and Linux.
#   XVID      — AVI container. Widely available cross-platform.
#   MJPG      — Universally supported AVI fallback of last resort (large files).
NON_WEB_CODECS = ["mp4v", "XVID", "MJPG"]

WEB_COMPATIBLE_AV_CODEC_NAMES = ['h264', 'hevc', 'vp8', 'vp9', 'av1']

# Fourcc codes as reported by cv2.VideoCapture when *reading* web-compatible
# files.  cv2's read-back fourcc can differ from the writer fourcc (e.g. a file
# written with 'X264' is typically read back as 'avc1').  Stored lowercase so
# the comparison in is_web_compatible_file() can be case-insensitive.
_WEB_COMPATIBLE_READ_FOURCCS_LOWER = [
    'avc1', 'h264', 'x264',   # H.264 variants
    'hvc1', 'hev1', 'hevc',   # HEVC variants
    'vp80',                    # VP8
    'vp90', 'vp09',            # VP9 variants
    'av01',                    # AV1
]

_CODEC_PROBE_TIMEOUT_SECONDS = 5

# Canonical fourcc → container-extension map. Single source of truth used by
# both the recorder (when writing) and RecordingInfo (when resolving paths).
#
# A "fourcc" is a 4-character codec identifier OpenCV passes to its underlying
# video backend (FFmpeg on Linux/Mac, Media Foundation on Windows). The same
# codec sometimes has multiple fourccs depending on which backend implements
# it, which is why several entries below map to the same container.
FOURCC_TO_EXTENSION: dict[str, str] = {
    # pyav/libx264 path — used when OpenCV cannot encode H264 natively
    PYAV_H264_FOURCC: 'mp4',
    # --- MP4 (H.264) — best compression, best compatibility ---
    'X264': 'mp4',  # H.264 via libx264 (FFmpeg). Bundled with OpenCV on Windows;
                    # typically NOT in pip-installed OpenCV on Linux/macOS.
    'H264': 'mp4',  # Generic H.264 fourcc. Backend picks an implementation
                    # (libx264, OS-native, hardware). Works where X264 does, and
                    # sometimes elsewhere when the backend has a non-libx264 H.264.
    'avc1': 'mp4',  # H.264 via Apple VideoToolbox — Mac-native MP4 path,
                    # hardware-accelerated, no libx264 needed.

    # --- MP4 (MPEG-4 Part 2) — older codec, very widely available ---
    'mp4v': 'mp4',  # MPEG-4 Part 2 (ISO/IEC 14496-2). Predecessor to H.264;
                    # less efficient but ships with virtually every FFmpeg
                    # build, so it's a reliable MP4 fallback when H.264 isn't.
    'MP4V': 'mp4',  # Same codec as 'mp4v'; uppercase variant some backends emit.

    # --- AVI (older Microsoft container) — fallback when MP4 is unavailable ---
    'XVID': 'avi',  # XviD / MPEG-4 ASP in AVI. Open-source, cross-platform,
                    # and one of the most reliable AVI codecs.
    'DIVX': 'avi',  # DivX MPEG-4. Closely related to XviD; legacy support.
    'MJPG': 'avi',  # Motion JPEG — every frame is a standalone JPEG. Universally
                    # supported (last-resort fallback) but produces very large
                    # files since there is no inter-frame compression.
}

class _CodecProbeTimeout(Exception):
    pass

def _check_pyav_libx264() -> bool:
    """Return True if pyav's bundled FFmpeg can encode H264 with libx264."""
    try:
        import av
        av.codec.Codec('libx264', 'w')
        return True
    except Exception:
        return False



def _probe_codec(fourcc_str: str, frame_size: tuple[int, int]) -> bool:
    """Return True if cv2.VideoWriter can write a frame with this codec.

    Uses a unique temp file per call to avoid race conditions when multiple
    camera worker processes probe codecs simultaneously.  Times out after
    _CODEC_PROBE_TIMEOUT_SECONDS to avoid hanging on broken codec backends.
    """
    logger.debug(f"Probing video codec '{fourcc_str}' with frame size {frame_size}...")
    if fourcc_str == PYAV_H264_FOURCC:
        return _check_pyav_libx264()
    
    ext = FOURCC_TO_EXTENSION.get(fourcc_str, "avi")
    fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", prefix="_skellycam_codec_probe_")
    os.close(fd)
    test_frame = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
    writer: cv2.VideoWriter | None = None

    def _timeout_handler(signum: int, frame: object) -> None:
        raise _CodecProbeTimeout(f"Codec probe for '{fourcc_str}' timed out after {_CODEC_PROBE_TIMEOUT_SECONDS}s")

    old_handler = None
    if sys.platform != "win32":
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(_CODEC_PROBE_TIMEOUT_SECONDS)

    try:
        writer = cv2.VideoWriter(
            tmp_path,
            cv2.VideoWriter.fourcc(*fourcc_str),
            30.0,
            frame_size,
        )
        if not writer.isOpened():
            logger.debug(f"Codec '{fourcc_str}' failed: writer did not open")
            return False
        writer.write(test_frame)
        writer.release()
        writer = None
        # Verify the file has actual content (some backends open but write nothing)
        ok = Path(tmp_path).stat().st_size >= 100
        logger.debug(f"Codec '{fourcc_str}' probe {'succeeded' if ok else 'failed (empty file)'}")
        return ok
    except _CodecProbeTimeout:
        logger.warning(f"Codec '{fourcc_str}' probe timed out — skipping")
        return False
    except Exception as e:
        logger.debug(f"Codec '{fourcc_str}' probe failed with {type(e).__name__}: {e}")
        return False
    finally:
        if sys.platform != "win32":
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        if writer is not None:
            writer.release()
        Path(tmp_path).unlink(missing_ok=True)




def resolve_writer_fourcc(requested_fourcc: str, frame_size: tuple[int, int]) -> str:
    """Return a working fourcc string for cv2.VideoWriter, or PYAV_H264_FOURCC to
    signal that _PyavVideoWriter should be used instead.

    Priority:
    1. Requested codec (if it works with OpenCV)
    2. Web-compatible OpenCV codecs: X264, H264, avc1, pyav/libx264 
    3. Non-web-compatible OpenCV codecs: mp4v, XVID, MJPG (last resort)

    Raises RuntimeError if nothing works at all.
    """
    if _probe_codec(fourcc_str=requested_fourcc, frame_size=frame_size):
        return requested_fourcc

    logger.warning(
        f"Requested video codec '{requested_fourcc}' is not available on this system. "
        f"Probing web-compatible fallbacks: {WEB_COMPATIBLE_CODECS}"
    )

    for fourcc_str in WEB_COMPATIBLE_CODECS:
        if fourcc_str == requested_fourcc:
            continue
        if _probe_codec(fourcc_str=fourcc_str, frame_size=frame_size):
            logger.info(f"Using fallback video codec: {fourcc_str}")
            return fourcc_str

    logger.warning(
        f"No web-compatible codec available. Falling back to non-web-compatible codecs: "
        f"{NON_WEB_CODECS}. Recorded videos may not play in the browser."
    )
    for fourcc_str in NON_WEB_CODECS:
        if fourcc_str == requested_fourcc:
            continue
        if _probe_codec(fourcc_str=fourcc_str, frame_size=frame_size):
            logger.info(f"Using fallback video codec: {fourcc_str}")
            return fourcc_str

    raise RuntimeError(
        f"No usable video writer codec found (tried '{requested_fourcc}', "
        f"{WEB_COMPATIBLE_CODECS} and {NON_WEB_CODECS}). "
        f"Ensure OpenCV is built with FFmpeg support or install codec libraries."
    )

def is_web_compatible_file(video_path: Path) -> bool:
    """Return True if the video at *video_path* uses a Chromium-playable codec.

    Probes via cv2.VideoCapture — no av import required.
    Returns False on any read error so the caller can fall back gracefully.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    cap.release()
    fourcc_str = ''.join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)).rstrip('\x00')
    return fourcc_str.lower() in _WEB_COMPATIBLE_READ_FOURCCS_LOWER
