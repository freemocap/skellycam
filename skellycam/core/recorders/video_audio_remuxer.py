import json
import logging
import shutil
from fractions import Fraction
from pathlib import Path

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


def remux_video_with_audio_and_timestamps(
    video_path: str,
    audio_path: str | None,
    frame_timestamps_perf_ns: list[int],
    audio_start_perf_ns: int | None,
    metadata_json: dict,
) -> None:
    """Remux a video file to add:
    - Variable frame rate PTS from real capture timestamps
    - Audio track (if audio_path provided) with sync offset baked into PTS
    - Recording metadata as an MP4 global metadata tag

    Video is decoded and re-encoded for VFR PTS and cross-version compatibility.
    Audio is encoded to AAC. The original file is replaced with the remuxed version.
    """
    output_path = video_path + ".remux.mp4"

    try:
        _do_remux(
            video_path=video_path,
            audio_path=audio_path,
            output_path=output_path,
            frame_timestamps_perf_ns=frame_timestamps_perf_ns,
            audio_start_perf_ns=audio_start_perf_ns,
            metadata_json=metadata_json,
        )
        shutil.move(output_path, video_path)
        logger.info(f"Remuxed: {video_path}")
    except Exception:
        # Clean up partial output on failure — use missing_ok for safety
        Path(output_path).unlink(missing_ok=True)
        raise


def _do_remux(
    video_path: str,
    audio_path: str | None,
    output_path: str,
    frame_timestamps_perf_ns: list[int],
    audio_start_perf_ns: int | None,
    metadata_json: dict,
) -> None:
    import av  # lazy import: keeps av out of the main process until remuxing actually runs (potentially causing problems with opencv on macos)
    video_in = av.open(video_path)
    audio_in = None
    output = av.open(output_path, mode="w")

    try:
        v_in_stream = video_in.streams.video[0]

        # Embed recording metadata as a global MP4 tag
        output.metadata["skellycam_data"] = json.dumps(metadata_json)

        # --- Video stream: decode + re-encode with VFR PTS ---
        VIDEO_TIMEBASE = Fraction(1, 90000)

        v_out_stream = output.add_stream("libx264", rate=30)
        v_out_stream.width = v_in_stream.codec_context.width
        v_out_stream.height = v_in_stream.codec_context.height
        v_out_stream.pix_fmt = "yuv420p"
        v_out_stream.time_base = VIDEO_TIMEBASE
        v_out_stream.options = {"crf": "18", "preset": "fast"}

        # Convert perf_counter_ns timestamps to PTS in video timebase
        if frame_timestamps_perf_ns:
            t0 = frame_timestamps_perf_ns[0]
            video_pts_values = [
                int((ts - t0) / 1e9 * 90000)
                for ts in frame_timestamps_perf_ns
            ]
        else:
            video_pts_values = []

        # --- Audio stream: encode WAV to AAC with sync offset ---
        a_out_stream = None
        audio_offset_samples = 0

        if audio_path and Path(audio_path).exists() and audio_start_perf_ns is not None:
            audio_in = av.open(audio_path)
            a_in_stream = audio_in.streams.audio[0]
            a_out_stream = output.add_stream("aac", rate=a_in_stream.rate)
            a_out_stream.layout = "stereo" if a_in_stream.channels >= 2 else "mono"

            # Compute audio offset relative to first video frame.
            # Positive = audio started after video, negative = audio started before.
            if frame_timestamps_perf_ns:
                offset_ns = audio_start_perf_ns - frame_timestamps_perf_ns[0]
                audio_offset_samples = int(offset_ns / 1e9 * a_in_stream.rate)
                logger.debug(f"Audio sync offset: {offset_ns / 1e6:.1f}ms ({audio_offset_samples} samples)")

        # Decode video, apply VFR PTS, re-encode
        frame_idx = 0
        for frame in video_in.decode(v_in_stream):
            if frame_idx < len(video_pts_values):
                frame.pts = video_pts_values[frame_idx]
                frame.time_base = VIDEO_TIMEBASE
            frame_idx += 1
            for packet in v_out_stream.encode(frame):
                output.mux(packet)

        # Flush video encoder
        for packet in v_out_stream.encode():
            output.mux(packet)

        if frame_idx != len(video_pts_values):
            logger.warning(
                f"Video had {frame_idx} frames but {len(video_pts_values)} timestamps — "
                f"PTS may be inaccurate for some frames"
            )

        # Encode and mux audio with offset PTS
        if audio_in and a_out_stream:
            for frame in audio_in.decode(audio_in.streams.audio[0]):
                if frame.pts is not None:
                    adjusted_pts = frame.pts + audio_offset_samples
                    # Skip audio frames that fall before the first video frame
                    if adjusted_pts < 0:
                        continue
                    frame.pts = adjusted_pts
                for packet in a_out_stream.encode(frame):
                    output.mux(packet)

            # Flush audio encoder
            for packet in a_out_stream.encode():
                output.mux(packet)

    finally:
        # Always close all containers to release file handles (critical on Windows)
        output.close()
        video_in.close()
        if audio_in is not None:
            audio_in.close()


def load_frame_timestamps_from_csv(csv_path: str) -> list[int]:
    """Load per-frame perf_counter_ns timestamps from a camera timestamp CSV."""
    df = pl.read_csv(csv_path)
    ts_col = "timestamp.perf_counter_ns.ns"
    if ts_col not in df.columns:
        raise ValueError(
            f"Expected column '{ts_col}' in {csv_path}, "
            f"found columns: {df.columns}"
        )
    return df[ts_col].cast(pl.Int64).to_list()


def load_audio_start_time(audio_timestamps_path: str) -> int:
    """Load the audio recording start perf_counter_ns from the timestamp sidecar."""
    with open(audio_timestamps_path, "r") as f:
        data = json.load(f)
    return int(data["start_perf_counter_ns"])
