"""Hand Rust capture timing to SkellyCam's shared recording finalizer."""
import csv
from pathlib import Path

import numpy as np

from skellycam.core.recorders.recording_finalizer import RecordingFinalizer
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE

# Lifecycle events only the Rust backend has (skellycam-rust timestamps/csv_writer.rs). They stay in each
# camera's timestamps file as `frame.<event>.ns`, like the shared lifecycle columns.
RUST_ONLY_LIFECYCLE_EVENTS = (
    "copied_from_driver_ns",
    "sent_to_multiframe_ns",
    "received_by_multiframe_ns",
    "pre_write_to_video_encoder_ns",
    "post_write_to_video_encoder_ns",
)


async def finalize_rust_recording(*, summary, recording_info, camera_configs, timebase):
    """Read each camera's timing CSV that Rust wrote at its standard path, then let the shared finalizer
    rewrite it in the standard per-camera layout."""
    written = {Path(path).resolve() for path in summary["csv_paths"]}
    if len(written) != len(camera_configs):
        raise ValueError(f"Rust wrote {len(written)} timestamp files for {len(camera_configs)} cameras")
    by_camera, rust_only_by_camera = {}, {}
    for camera_id, config in camera_configs.items():
        csv_path = Path(recording_info.camera_timestamps_file_path_from_camera_id(camera_id))
        if csv_path.resolve() not in written:
            raise ValueError(f"Rust recorded no timestamps for camera {camera_id} at {csv_path}")
        rows = []
        rust_only = {name: [] for name in RUST_ONLY_LIFECYCLE_EVENTS}
        with csv_path.open(encoding="utf-8", newline="") as stream:
            for source in csv.DictReader(stream):
                metadata = np.zeros(1, dtype=FRAME_METADATA_DTYPE).view(np.recarray)
                metadata.camera_info.camera_id = camera_id
                metadata.camera_info.camera_index = config.camera_index
                metadata.camera_info.rotation = config.rotation.value
                metadata.camera_info.color_channels = config.color_channels
                metadata.frame_number = int(source["frame_number"])
                metadata.timebase_mapping = timebase.to_numpy_record_array()
                # The frame-grab bracket means the same in both backends: the capture loop starts waiting
                # for the next frame (Rust: barrier exit) and the next frame is available to the loop
                # (Rust: first poll with Cap_hasNewFrame true). The other shared lifecycle fields name
                # OpenCV-backend events; they stay 0 and are not reported.
                metadata.timestamps["pre_frame_grab_ns"] = int(source["pre_frame_grab_ns"])
                metadata.timestamps["post_frame_grab_ns"] = int(source["post_frame_grab_ns"])
                rows.append(metadata)
                for name in RUST_ONLY_LIFECYCLE_EVENTS:
                    rust_only[name].append(int(source[name]))
        if not rows:
            raise ValueError(f"Rust camera {camera_id} recorded no timestamps")
        by_camera[camera_id] = rows
        rust_only_by_camera[camera_id] = {name: np.asarray(values, dtype=np.int64)
                                          for name, values in rust_only.items()}
    return await RecordingFinalizer.create(
        recording_info=recording_info,
        camera_configs=camera_configs,
        frame_metadatas_by_camera=by_camera,
        additional_lifecycle_timestamps_by_camera=rust_only_by_camera,
    ).finalize_recording()
