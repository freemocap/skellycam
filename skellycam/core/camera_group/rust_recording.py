"""Map native capture evidence into SkellyCam's shared recording finalizer."""
import csv
import json
from pathlib import Path

import numpy as np

from skellycam.core.recorders.recording_finalizer import RecordingFinalizer
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE


async def finalize_native_recording(*, summary, recording_info, camera_configs, timebase):
    native = json.loads(Path(summary["info_json_path"]).read_text(encoding="utf-8"))
    csv_paths = {Path(value).name: Path(value) for value in summary["csv_paths"]}
    by_camera = {}
    for camera in native["cameras"]:
        camera_id = camera["unique_identifier"]
        config = camera_configs[camera_id]
        rows = []
        with csv_paths[camera["timestamp_csv_path"]].open(encoding="utf-8", newline="") as stream:
            for source in csv.DictReader(stream):
                metadata = np.zeros(1, dtype=FRAME_METADATA_DTYPE).view(np.recarray)
                metadata.camera_info.camera_id = camera_id
                metadata.camera_info.camera_index = config.camera_index
                metadata.camera_info.rotation = config.rotation.value
                metadata.camera_info.color_channels = config.color_channels
                metadata.frame_number = int(source["frame_number"])
                metadata.timebase_mapping = timebase.to_numpy_record_array()
                # Rust queues replace Python shared memory. Preserve the native
                # CSV; map measured send/receive endpoints to the common transport
                # stage. Rust has no separate initialization or retrieve wait.
                mapping = {
                    "initialized_ns": "loop_start_ns",
                    "pre_frame_grab_ns": "loop_start_ns",
                    "post_frame_grab_ns": "frame_available_ns",
                    "pre_frame_retrieve_ns": "frame_available_ns",
                    "post_frame_retrieve_ns": "post_jpeg_extract_ns",
                    "pre_copy_to_camera_shm_ns": "pre_send_ns",
                    "post_copy_to_camera_shm_ns": "gatherer_received_ns",
                    "pre_frame_record_ns": "pre_frame_record_ns",
                    "post_frame_record_ns": "post_frame_record_ns",
                }
                for destination, origin in mapping.items():
                    metadata.timestamps[destination] = int(source[f"timestamps.{origin}"])
                rows.append(metadata)
        if not rows:
            raise ValueError(f"Native camera {camera_id} recorded no timestamps")
        by_camera[camera_id] = rows
    if set(by_camera) != set(camera_configs):
        raise ValueError("Native recording is missing one or more configured cameras")
    return await RecordingFinalizer.create(
        recording_info=recording_info,
        camera_configs=camera_configs,
        frame_metadatas_by_camera=by_camera,
    ).finalize_recording()
