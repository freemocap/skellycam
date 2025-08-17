# Remove the nested duplicate class and move the __str__ method to the top-level class
import dataclasses
import json
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import calculate_statistics
from skellycam.core.camera_group.timestamps.recording_timestamps import RecordingTimestamps
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import MULTI_FRAME_TIMESTAMP_CSV_ROW
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics


@dataclass
class RecordingTimestampsStats:
    """
    A class to hold statistics about timestamps in a recording session.
    This is used to generate statistics about the recording timestamps.
    """
    recording_info: RecordingInfo
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    framerate_stats: np.recarray

    frame_duration_stats: np.recarray
    inter_camera_grab_range_ms: np.recarray

    idle_before_frame_grab_ms: np.recarray
    during_frame_grab_ms: np.recarray
    idle_before_retrieve_ms: np.recarray
    during_frame_retrieve_ms: np.recarray
    idle_before_copy_to_camera_shm_ms: np.recarray
    during_copy_to_camera_shm_ms: np.recarray
    idle_before_frame_record_ms: np.recarray
    during_frame_record_ms: np.recarray
    total_frame_processing_time_ms: np.recarray
    total_camera_idle_time_ms: np.recarray

    @classmethod
    def from_multiframe_rows(cls, multiframe_rows: np.recarray,
                             recording_info: RecordingInfo,
                             number_of_cameras: int) -> 'RecordingTimestampsStats':
        if multiframe_rows.dtype != MULTI_FRAME_TIMESTAMP_CSV_ROW:
            raise ValueError(f"Expected dtype {MULTI_FRAME_TIMESTAMP_CSV_ROW}, got {multiframe_rows.dtype}")

        return cls(
            recording_info = recording_info,
            number_of_cameras = number_of_cameras,
            number_of_frames = multiframe_rows.shape[0],
            total_duration_sec = multiframe_rows[-1]['timestamp.from_recording_start.sec'],
            framerate_stats = calculate_statistics(data=multiframe_rows['from_previous.framerate.hz'], axis=0),
            frame_duration_stats = calculate_statistics(data=multiframe_rows['from_previous.frame_duration.ms'], axis=0),
            inter_camera_grab_range_ms = calculate_statistics(data=multiframe_rows['inter_camera.frame_grab_range.ms'], axis=0),

            idle_before_frame_grab_ms = calculate_statistics(data=multiframe_rows['duration.idle_before_frame_grab.ms.median'], axis=0),
            during_frame_grab_ms = calculate_statistics(data=multiframe_rows['duration.during_frame_grab.ms.median'], axis=0),
            idle_before_retrieve_ms = calculate_statistics(data=multiframe_rows['duration.idle_before_retrieve.ms.median'], axis=0),
            during_frame_retrieve_ms = calculate_statistics(data=multiframe_rows['duration.during_frame_retrieve.ms.median'], axis=0),
            idle_before_copy_to_camera_shm_ms = calculate_statistics(data=multiframe_rows['duration.idle_before_copy_to_camera_shm.ms.median'], axis=0),
            during_copy_to_camera_shm_ms = calculate_statistics(data=multiframe_rows['duration.during_copy_to_camera_shm.ms.median'], axis=0),
            idle_before_frame_record_ms = calculate_statistics(data=multiframe_rows['duration.idle_before_frame_record.ms.median'], axis=0),
            during_frame_record_ms = calculate_statistics(data=multiframe_rows['duration.during_frame_record.ms.median'], axis=0),
            total_frame_processing_time_ms = calculate_statistics(data=multiframe_rows['total.frame_processing_time.ms.median'], axis=0),
            total_camera_idle_time_ms = calculate_statistics(data=multiframe_rows['total.camera_idle_time.ms.median'], axis=0),
        )

    def to_json(self, exclude: set[str] = None, indent: int = None) -> str:
        """
        Convert the dataclass to a JSON string, similar to Pydantic's model_dump_json.

        Args:
            exclude: Set of field names to exclude from the JSON output
            indent: Number of spaces for indentation in the JSON output

        Returns:
            JSON string representation of the dataclass
        """
        exclude = exclude or set()

        # Convert dataclass to dict, excluding specified fields
        def dataclass_to_dict(obj):
            if dataclasses.is_dataclass(obj):
                result = {}
                for field in dataclasses.fields(obj):
                    if field.name not in exclude:
                        value = getattr(obj, field.name)

                        result[field.name.replace('_value', '')] = dataclass_to_dict(value)
                return result
            elif isinstance(obj, list):
                return [dataclass_to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: dataclass_to_dict(value) for key, value in obj.items()}
            else:
                return obj

        # Convert to dict and then to JSON
        obj_dict = dataclass_to_dict(self)
        return json.dumps(obj_dict, indent=indent, default=lambda o: o.__dict__)

    def __str__(self):
        """
        Create an attractive and informative string representation of the stats using Python's string templates.
        This approach makes the output more maintainable and debuggable.
        """
        from string import Template
        from tabulate import tabulate

        # Set precision for consistent decimal places
        precision = 3

        # Create timing table
        timing_data = [
            ["Framerate/FPS (Hz)",
             f"{self.framerate_stats.median_value:.{precision}f}",
             f"{self.framerate_stats.mean_value:.{precision}f}",
             f"{self.framerate_stats.standard_deviation_value:.{precision}f}",
             f"{self.framerate_stats.min_value:.{precision}f}",
             f"{self.framerate_stats.max_value:.{precision}f}",
             ],
            ["Frame Duration (ms)",
             f"{self.frame_duration_stats.median_value:.{precision}f}",
             f"{self.frame_duration_stats.mean_value:.{precision}f}",
             f"{self.frame_duration_stats.standard_deviation_value:.{precision}f}",
             f"{self.frame_duration_stats.min_value:.{precision}f}",
             f"{self.frame_duration_stats.max_value:.{precision}f}",
             ],
            ["Inter-Camera Frame Grab Sync (ms)",
             f"{self.inter_camera_grab_range_ms.median_value:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.mean_value:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.standard_deviation_value:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.min_value:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.max_value:.{precision}f}",
             ]
        ]

        timing_table = tabulate(
            timing_data,
            headers=["Metric", "Median", "Mean", "Std", "Min", "Max"],
            tablefmt="rst",
            floatfmt=f".{precision}f"
        )

        # Calculate total time for percentage calculations


        # Create processing table data
        processing_stages_table_data = []

        # Add Camera Frame Acquisition stages
        processing_stages = [
            ("During frame grab", self.during_frame_grab_ms),
            ("Idle before retrieve", self.idle_before_retrieve_ms),
            ("During frame retrieve", self.during_frame_retrieve_ms),
            ("Idle before copy to camera SHM", self.idle_before_copy_to_camera_shm_ms),
            ("During copy to camera SHM", self.during_copy_to_camera_shm_ms),
            ("Idle before frame record", self.idle_before_frame_record_ms),
            ("During frame record", self.during_frame_record_ms),
        ]

        median_total_processing_time = sum(stage.median_value for _, stage in processing_stages)
        for stage_name, stats in processing_stages:
            percentage = (stats.median_value / median_total_processing_time) * 100 if median_total_processing_time > 0 else 0
            processing_stages_table_data.append([
                stage_name,
                f"{stats.median_value:.{precision}f}",
                f"{stats.mean_value:.{precision}f}",
                f"{stats.standard_deviation_value:.{precision}f}",
                f"{stats.min_value:.{precision}f}",
                f"{stats.max_value:.{precision}f}",
                f"{percentage:.1f}%"
            ])

        # Add a separator line before the total
        processing_stages_table_data.append(["═" * 25, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 10])

        # Add Total Processing Time with highlighting
        total_processing_stats = self.total_frame_processing_time_ms
        # Add Total Camera Idle Time
        total_idle_stats = self.total_camera_idle_time_ms

        total_time = total_processing_stats.median_value + total_idle_stats.median_value
        processing_percentage = (total_processing_stats.median_value / total_time) * 100
        idle_percentage = (total_idle_stats.median_value / total_time) * 100

        processing_stages_table_data.append([
            "TOTAL FRAME PROCESSING TIME",
            f"{total_processing_stats.median_value:.{precision}f}",
            f"{total_processing_stats.mean_value:.{precision}f}",
            f"{total_processing_stats.standard_deviation_value:.{precision}f}",
            f"{total_processing_stats.min_value:.{precision}f}",
            f"{total_processing_stats.max_value:.{precision}f}",
            f"{processing_percentage:.1f}%"
        ])

        processing_stages_table_data.append([
            "TOTAL CAMERA IDLE TIME",
            f"{total_idle_stats.median_value:.{precision}f}",
            f"{total_idle_stats.mean_value:.{precision}f}",
            f"{total_idle_stats.standard_deviation_value:.{precision}f}",
            f"{total_idle_stats.min_value:.{precision}f}",
            f"{total_idle_stats.max_value:.{precision}f}",
            f"{idle_percentage:.1f}%"
        ])

        processing_table = tabulate(
            processing_stages_table_data,
            headers=["Stage", "Median (ms)", "Mean (ms)", "Std (ms)", "Min (ms)", "Max (ms)", "% of Processing Time"],
            tablefmt="rst",
            floatfmt=f".{precision}f"
        )

        # Calculate efficiency metrics
        processing_ratio = (self.total_frame_processing_time_ms.median_value / median_total_processing_time) * 100 if median_total_processing_time > 0 else 0

        # Define the template as a multi-line string
        template_str = """$separator
Timestamp Statistics for recording: $recording_name

Number of Cameras: $num_cameras
Total Frames: $num_frames
Total Duration: $duration seconds

FRAME TIMING STATISTICS
$timing_table

FRAME PROCESSING TIMESTAMPS
$processing_table
    """

        # Create a template and substitute values
        template = Template(template_str)
        return template.substitute(
            separator="_" * 80,
            recording_name=self.recording_info.recording_name,
            num_cameras=self.number_of_cameras,
            num_frames=self.number_of_frames,
            duration=f"{self.total_duration_sec:.3f}",
            timing_table=timing_table,
            processing_table=processing_table,
            proc_ratio=f"{processing_ratio:.1f}",
            idle_ratio=f"{(100 - processing_ratio):.1f}",
            avg_fps=f"{self.framerate_stats.mean_value:.2f}",
            sync_ms=f"{self.inter_camera_grab_range_ms.mean_value:.2f}"
        )