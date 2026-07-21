import dataclasses
import json
from dataclasses import dataclass
from string import Template

import numpy as np
from tabulate import tabulate

from skellycam.core.timestamps.numpy_timestamps.calculate_timestamps_numpy import calculate_statistics
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import MULTI_FRAME_TIMESTAMP_CSV_ROW

REPORT_PRECISION: int = 3
SEPARATOR_WIDTH: int = 80


def _format_stats_row(
    stage_name: str,
    stats: np.recarray,
    percentage: float,
    precision: int = REPORT_PRECISION,
) -> list[str]:
    """Format a single row of the processing stages table."""
    return [
        stage_name,
        f"{stats.median_value:.{precision}f}",
        f"{stats.mean_value:.{precision}f}",
        f"{stats.standard_deviation_value:.{precision}f}",
        f"{stats.min_value:.{precision}f}",
        f"{stats.max_value:.{precision}f}",
        f"{percentage:.1f}%",
    ]


@dataclass
class RecordingTimestampsStats:
    """Statistics about frame lifecycle timestamps in a recording session.

    Created from the multiframe CSV rows after a recording is finalized.
    Provides both JSON serialization (for machine consumption) and a
    human-readable text report (via __str__).
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
    def from_multiframe_rows(
        cls,
        multiframe_rows: np.recarray,
        recording_info: RecordingInfo,
        number_of_cameras: int,
    ) -> "RecordingTimestampsStats":
        if multiframe_rows.dtype != MULTI_FRAME_TIMESTAMP_CSV_ROW:
            raise ValueError(
                f"Expected dtype {MULTI_FRAME_TIMESTAMP_CSV_ROW}, got {multiframe_rows.dtype}"
            )

        return cls(
            recording_info=recording_info,
            number_of_cameras=number_of_cameras,
            number_of_frames=multiframe_rows.shape[0],
            total_duration_sec=multiframe_rows[-1]["timestamp.from_recording_start.sec"],
            framerate_stats=calculate_statistics(
                data=multiframe_rows["from_previous.framerate.hz"], axis=0
            ),
            frame_duration_stats=calculate_statistics(
                data=multiframe_rows["from_previous.frame_duration.ms"], axis=0
            ),
            inter_camera_grab_range_ms=calculate_statistics(
                data=multiframe_rows["inter_camera.frame_grab_range.ms"], axis=0
            ),
            idle_before_frame_grab_ms=calculate_statistics(
                data=multiframe_rows["duration.idle_before_frame_grab.ms.median"], axis=0
            ),
            during_frame_grab_ms=calculate_statistics(
                data=multiframe_rows["duration.during_frame_grab.ms.median"], axis=0
            ),
            idle_before_retrieve_ms=calculate_statistics(
                data=multiframe_rows["duration.idle_before_retrieve.ms.median"], axis=0
            ),
            during_frame_retrieve_ms=calculate_statistics(
                data=multiframe_rows["duration.during_frame_retrieve.ms.median"], axis=0
            ),
            idle_before_copy_to_camera_shm_ms=calculate_statistics(
                data=multiframe_rows["duration.idle_before_copy_to_camera_shm.ms.median"],
                axis=0,
            ),
            during_copy_to_camera_shm_ms=calculate_statistics(
                data=multiframe_rows["duration.during_copy_to_camera_shm.ms.median"], axis=0
            ),
            idle_before_frame_record_ms=calculate_statistics(
                data=multiframe_rows["duration.idle_before_frame_record.ms.median"], axis=0
            ),
            during_frame_record_ms=calculate_statistics(
                data=multiframe_rows["duration.during_frame_record.ms.median"], axis=0
            ),
            total_frame_processing_time_ms=calculate_statistics(
                data=multiframe_rows["total.frame_processing_time.ms.median"], axis=0
            ),
            total_camera_idle_time_ms=calculate_statistics(
                data=multiframe_rows["total.camera_idle_time.ms.median"], axis=0
            ),
        )

    def to_json(self, exclude: set[str] | None = None, indent: int | None = None) -> str:
        """Serialize to JSON, converting numpy recarrays to plain dicts."""
        exclude = exclude or set()

        def _to_serializable(obj: object) -> object:
            if dataclasses.is_dataclass(obj):
                result = {}
                for field in dataclasses.fields(obj):
                    if field.name not in exclude:
                        value = getattr(obj, field.name)
                        result[field.name.replace("_value", "")] = _to_serializable(value)
                return result
            elif isinstance(obj, list):
                return [_to_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: _to_serializable(value) for key, value in obj.items()}
            else:
                return obj

        obj_dict = _to_serializable(self)
        return json.dumps(obj_dict, indent=indent, default=lambda o: o.__dict__)

    def _build_timing_table(self) -> str:
        """Build the frame timing statistics table (FPS, duration, inter-camera sync)."""
        p = REPORT_PRECISION
        timing_data = [
            [
                "Framerate/FPS (Hz)",
                f"{self.framerate_stats.median_value:.{p}f}",
                f"{self.framerate_stats.mean_value:.{p}f}",
                f"{self.framerate_stats.standard_deviation_value:.{p}f}",
                f"{self.framerate_stats.min_value:.{p}f}",
                f"{self.framerate_stats.max_value:.{p}f}",
            ],
            [
                "Frame Duration (ms)",
                f"{self.frame_duration_stats.median_value:.{p}f}",
                f"{self.frame_duration_stats.mean_value:.{p}f}",
                f"{self.frame_duration_stats.standard_deviation_value:.{p}f}",
                f"{self.frame_duration_stats.min_value:.{p}f}",
                f"{self.frame_duration_stats.max_value:.{p}f}",
            ],
            [
                "Inter-Camera Frame Grab Sync (ms)",
                f"{self.inter_camera_grab_range_ms.median_value:.{p}f}",
                f"{self.inter_camera_grab_range_ms.mean_value:.{p}f}",
                f"{self.inter_camera_grab_range_ms.standard_deviation_value:.{p}f}",
                f"{self.inter_camera_grab_range_ms.min_value:.{p}f}",
                f"{self.inter_camera_grab_range_ms.max_value:.{p}f}",
            ],
        ]

        return tabulate(
            timing_data,
            headers=["Metric", "Median", "Mean", "Std", "Min", "Max"],
            tablefmt="rst",
            floatfmt=f".{p}f",
        )

    def _build_processing_table(self) -> str:
        """Build the per-stage frame processing breakdown table."""
        processing_stages: list[tuple[str, np.recarray]] = [
            ("During frame grab", self.during_frame_grab_ms),
            ("Idle before retrieve", self.idle_before_retrieve_ms),
            ("During frame retrieve", self.during_frame_retrieve_ms),
            ("Idle before copy to camera SHM", self.idle_before_copy_to_camera_shm_ms),
            ("During copy to camera SHM", self.during_copy_to_camera_shm_ms),
            ("Idle before frame record", self.idle_before_frame_record_ms),
            ("During frame record", self.during_frame_record_ms),
        ]

        median_stage_total = sum(stage.median_value for _, stage in processing_stages)

        rows: list[list[str]] = []
        for stage_name, stats in processing_stages:
            pct = (
                (stats.median_value / median_stage_total) * 100
                if median_stage_total > 0
                else 0
            )
            rows.append(_format_stats_row(stage_name=stage_name, stats=stats, percentage=pct))

        # Separator
        rows.append(["═" * 25, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 10])

        # Totals
        total_processing = self.total_frame_processing_time_ms
        total_idle = self.total_camera_idle_time_ms
        total_time = total_processing.median_value + total_idle.median_value

        if total_time > 0:
            processing_pct = (total_processing.median_value / total_time) * 100
            idle_pct = (total_idle.median_value / total_time) * 100
        else:
            processing_pct = 0.0
            idle_pct = 0.0

        rows.append(
            _format_stats_row(
                stage_name="TOTAL FRAME PROCESSING TIME",
                stats=total_processing,
                percentage=processing_pct,
            )
        )
        rows.append(
            _format_stats_row(
                stage_name="TOTAL CAMERA IDLE TIME",
                stats=total_idle,
                percentage=idle_pct,
            )
        )

        return tabulate(
            rows,
            headers=[
                "Stage",
                "Median (ms)",
                "Mean (ms)",
                "Std (ms)",
                "Min (ms)",
                "Max (ms)",
                "% of Total",
            ],
            tablefmt="rst",
            floatfmt=f".{REPORT_PRECISION}f",
        )

    def __str__(self) -> str:
        """Human-readable text report of recording timestamp statistics."""
        timing_table = self._build_timing_table()
        processing_table = self._build_processing_table()

        template_str = """\
$separator
Timestamp Statistics for recording: $recording_name

Number of Cameras: $num_cameras
Total Frames:      $num_frames
Total Duration:    $duration seconds
Mean Framerate:    $avg_fps Hz
Mean Inter-Camera Sync: $sync_ms ms

FRAME TIMING STATISTICS
$timing_table

FRAME PROCESSING BREAKDOWN
$processing_table
$separator"""

        template = Template(template_str)
        return template.substitute(
            separator="─" * SEPARATOR_WIDTH,
            recording_name=self.recording_info.recording_name,
            num_cameras=self.number_of_cameras,
            num_frames=self.number_of_frames,
            duration=f"{self.total_duration_sec:.3f}",
            timing_table=timing_table,
            processing_table=processing_table,
            avg_fps=f"{self.framerate_stats.mean_value:.2f}",
            sync_ms=f"{self.inter_camera_grab_range_ms.mean_value:.2f}",
        )
