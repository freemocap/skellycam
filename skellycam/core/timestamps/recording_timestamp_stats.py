# Remove the nested duplicate class and move the __str__ method to the top-level class
from pydantic import BaseModel
from tabulate import tabulate

from skellycam.core.timestamps.recording_timestamps import RecordingTimestamps
from skellycam.utilities.sample_statistics import DescriptiveStatistics


class RecordingTimestampsStats(BaseModel):
    """
    A class to hold statistics about timestamps in a recording session.
    This is used to generate statistics about the recording timestamps.
    """
    recording_name: str
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    framerate_stats: DescriptiveStatistics
    frame_duration_stats: DescriptiveStatistics
    inter_camera_grab_range_ms: DescriptiveStatistics
    idle_before_grab_ms: DescriptiveStatistics
    during_frame_grab_ms: DescriptiveStatistics
    idle_before_retrieve_ms: DescriptiveStatistics
    during_frame_retrieve_ms: DescriptiveStatistics
    idle_before_copy_to_camera_shm_ms: DescriptiveStatistics
    stored_in_camera_shm_ms: DescriptiveStatistics
    during_copy_from_camera_shm_ms: DescriptiveStatistics
    idle_before_copy_to_multiframe_shm_ms: DescriptiveStatistics
    stored_in_multiframe_shm_ms: DescriptiveStatistics
    during_copy_from_multiframe_shm_ms: DescriptiveStatistics
    total_frame_acquisition_time_ms: DescriptiveStatistics
    total_ipc_travel_time_ms: DescriptiveStatistics
    total_camera_to_recorder_time_ms: DescriptiveStatistics

    @classmethod
    def from_recording_timestamps(cls, recording_timestamps: RecordingTimestamps):
        return cls(
            recording_name=recording_timestamps.recording_info.recording_name,
            number_of_cameras=recording_timestamps.number_of_cameras,
            number_of_frames=recording_timestamps.number_of_recorded_frames,
            total_duration_sec=recording_timestamps.total_duration_sec,
            framerate_stats=recording_timestamps.framerate_stats,
            frame_duration_stats=recording_timestamps.frame_duration_stats,
            inter_camera_grab_range_ms=recording_timestamps.inter_camera_grab_range_stats,
            idle_before_grab_ms=recording_timestamps.idle_before_grab_duration_stats,
            during_frame_grab_ms=recording_timestamps.during_frame_grab_stats,
            idle_before_retrieve_ms=recording_timestamps.idle_before_retrieve_duration_stats,
            during_frame_retrieve_ms=recording_timestamps.during_frame_retrieve_stats,
            idle_before_copy_to_camera_shm_ms=recording_timestamps.idle_before_copy_to_camera_shm_stats,
            stored_in_camera_shm_ms=recording_timestamps.stored_in_camera_shm_stats,
            during_copy_from_camera_shm_ms=recording_timestamps.during_copy_from_camera_shm_stats,
            idle_before_copy_to_multiframe_shm_ms=recording_timestamps.idle_before_copy_to_multiframe_shm_stats,
            stored_in_multiframe_shm_ms=recording_timestamps.stored_in_multiframe_shm_stats,
            during_copy_from_multiframe_shm_ms=recording_timestamps.during_copy_from_multiframe_shm_stats,
            total_frame_acquisition_time_ms=recording_timestamps.total_frame_acquisition_time_stats,
            total_ipc_travel_time_ms=recording_timestamps.total_ipc_travel_time_stats,
            total_camera_to_recorder_time_ms=recording_timestamps.total_camera_to_recorder_time_stats
        )

    def __str__(self):
        """
        Create an attractive and informative string representation of the stats using tabulate,
        showing key statistics about recording timestamps and time spent in
        different stages of the frame acquisition process.
        """
        # Set precision for consistent decimal places
        precision = 3

        # Header with basic recording info
        header = "_" * 80 + "\n\n"
        header += f"Recording Statistics: {self.recording_name}\n\n"
        header += f"Number of Cameras: {self.number_of_cameras}\n"
        header += f"Total Frames: {self.number_of_frames}\n"
        header += f"Total Duration: {self.total_duration_sec:.3f} seconds\n\n"
        # Frame timing section with table for framerate, frame duration, and inter-camera timestamp range
        timing_section = "FRAME TIMING STATISTICS\n"

        # Create table for timing metrics with aligned decimals
        timing_data = [
            ["Framerate/FPS (Hz)",
             f"{self.framerate_stats.median:.{precision}f}",
             f"{self.framerate_stats.mean:.{precision}f}",
             f"{self.framerate_stats.standard_deviation:.{precision}f}",
             f"{self.framerate_stats.min:.{precision}f}",
             f"{self.framerate_stats.max:.{precision}f}",
             ],
            ["Frame Duration (ms)",
             f"{self.frame_duration_stats.median:.{precision}f}",
             f"{self.frame_duration_stats.mean:.{precision}f}",
             f"{self.frame_duration_stats.standard_deviation:.{precision}f}",
             f"{self.frame_duration_stats.min:.{precision}f}",
             f"{self.frame_duration_stats.max:.{precision}f}",
             ],
            ["Inter-Camera Frame Grab Sync (ms)",
             f"{self.inter_camera_grab_range_ms.median:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.mean:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.standard_deviation:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.min:.{precision}f}",
             f"{self.inter_camera_grab_range_ms.max:.{precision}f}",
             ]
        ]

        timing_table = tabulate(
            timing_data,
            headers=["Metric", "Median", "Mean", "Std", "Min", "Max"],
            tablefmt="rst",
            floatfmt=f".{precision}f"  # This ensures decimal alignment
        )
        timing_section += timing_table + "\n\n"

        # Frame acquisition pipeline section
        pipeline_section = "FRAME LIFESPAN TIMESTAMPS\n"

        # Calculate total time for percentage calculations
        total_time = self.total_camera_to_recorder_time_ms.mean


        # Create table data for pipeline stages, now with categories and subtotals
        idle_percentage = (self.idle_before_grab_ms.mean / total_time) * 100 if total_time > 0 else 0

        idle_data =[
            "Idle Before Grab Signal",
            f"{self.idle_before_grab_ms.median:.{precision}f}",
            f"{self.idle_before_grab_ms.mean:.{precision}f}",
            f"{self.idle_before_grab_ms.standard_deviation:.{precision}f}",
            f"{self.idle_before_grab_ms.min:.{precision}f}",
            f"{self.idle_before_grab_ms.max:.{precision}f}",
            f"{idle_percentage:.1f}%"
        ]
        table_data = [idle_data,
                      ["", "", "", "", "", "", ""]]

        # Add Camera Frame Acquisition stages
        acquisition_stages = [
            ("During frame grab", self.during_frame_grab_ms),
            ("Idle before retrieve", self.idle_before_retrieve_ms),
            ("During frame retrieve", self.during_frame_retrieve_ms),
        ]

        for stage_name, stats in acquisition_stages:
            percentage = (stats.mean / total_time) * 100 if total_time > 0 else 0
            table_data.append([
                stage_name,
                f"{stats.median:.{precision}f}",
                f"{stats.mean:.{precision}f}",
                f"{stats.standard_deviation:.{precision}f}",
                f"{stats.min:.{precision}f}",
                f"{stats.max:.{precision}f}",
                f"{percentage:.1f}%"
            ])

        # Add a separator line before the subtotal
        table_data.append(["─" * 25, "─" * 12, "─" * 12, "─" * 12, "─" * 12, "─" * 12, "─" * 10])

        # Add Camera Frame Acquisition subtotal with highlighting
        acquisition_total_median = self.total_frame_acquisition_time_ms.median
        acquisition_total_mean = self.total_frame_acquisition_time_ms.mean
        acquisition_percentage = (acquisition_total_mean / total_time) * 100 if total_time > 0 else 0
        table_data.append([
            "Subtotal (Acquisition)".upper(),
            f"{acquisition_total_median:.{precision}f}",
            f"{acquisition_total_mean:.{precision}f}",
            f"{self.total_frame_acquisition_time_ms.standard_deviation:.{precision}f}",
            f"{self.total_frame_acquisition_time_ms.min:.{precision}f}",
            f"{self.total_frame_acquisition_time_ms.max:.{precision}f}",
            f"{acquisition_percentage:.1f}%"
        ])

        table_data.append(["", "", "", "", "", "", ""])
        # Add IPC Transfer Pipeline category header
        table_data.append(["", "", "", "", "", "", ""],)

        # Add IPC Transfer Pipeline stages
        ipc_stages = [
            ("Idle before copy to camera SHM", self.idle_before_copy_to_camera_shm_ms),
            ("Stored in camera SHM", self.stored_in_camera_shm_ms),
            ("During copy from camera SHM", self.during_copy_from_camera_shm_ms),
            ("Idle before copy to multiframe SHM", self.idle_before_copy_to_multiframe_shm_ms),
            ("Stored in multiframe SHM", self.stored_in_multiframe_shm_ms),
            ("During copy from multiframe SHM", self.during_copy_from_multiframe_shm_ms),
        ]

        for stage_name, stats in ipc_stages:
            percentage = (stats.mean / total_time) * 100 if total_time > 0 else 0
            table_data.append([
                stage_name,
                f"{stats.median:.{precision}f}",
                f"{stats.mean:.{precision}f}",
                f"{stats.standard_deviation:.{precision}f}",
                f"{stats.min:.{precision}f}",
                f"{stats.max:.{precision}f}",
                f"{percentage:.1f}%"
            ])

        # Add a separator line before the subtotal
        table_data.append(["─" * 25, "─" * 12, "─" * 12, "─" * 12, "─" * 12, "─" * 12, "─" * 10])

        # Add IPC Transfer Pipeline subtotal with highlighting
        ipc_total_median = self.total_ipc_travel_time_ms.median
        ipc_total_mean = self.total_ipc_travel_time_ms.mean
        ipc_percentage = (ipc_total_mean / total_time) * 100 if total_time > 0 else 0
        table_data.append([
            "Subtotal (IPC)".upper(),
            f"{ipc_total_median:.{precision}f}",
            f"{ipc_total_mean:.{precision}f}",
            f"{self.total_ipc_travel_time_ms.standard_deviation:.{precision}f}",
            f"{self.total_ipc_travel_time_ms.min:.{precision}f}",
            f"{self.total_ipc_travel_time_ms.max:.{precision}f}",
            f"{ipc_percentage:.1f}%"
        ])

        # Add a double separator line before the total
        table_data.append(["═" * 25, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 10])

        # Add Total Camera-to-Recorder Time with highlighting
        total_stats = self.total_camera_to_recorder_time_ms
        # Use the calculated percentage, which should be close to 100% if measurements are accurate
        table_data.append([
            "Total Camera-to-Recorder Time".upper(),
            f"{total_stats.median:.{precision}f}",
            f"{total_stats.mean:.{precision}f}",
            f"{total_stats.standard_deviation:.{precision}f}",
            f"{total_stats.min:.{precision}f}",
            f"{total_stats.max:.{precision}f}",
            f"100%"
        ])
        # Create the pipeline table
        pipeline_table = tabulate(
            table_data,
            headers=["Stage", "Median (ms)", "Mean (ms)", "Std (ms)", "Min (ms)", "Max (ms)", "% of Total"],
            tablefmt="rst",
            floatfmt=f".{precision}f"  # This ensures decimal alignment
        )
        pipeline_section += pipeline_table + "\n\n"

        # Summary section with table
        summary_section = "-" * 80 + "\n"
        summary_section += "SUMMARY METRICS\n"

        summary_data = [
            ["frame acquisition time",
             f"{self.total_frame_acquisition_time_ms.median:.{precision}f}",
             f"{self.total_frame_acquisition_time_ms.mean:.{precision}f}",
             f"{self.total_frame_acquisition_time_ms.standard_deviation:.{precision}f}",
             f"{self.total_frame_acquisition_time_ms.min:.{precision}f}",
             f"{self.total_frame_acquisition_time_ms.max:.{precision}f}"],
            ["IPC travel time",
             f"{self.total_ipc_travel_time_ms.median:.{precision}f}",
             f"{self.total_ipc_travel_time_ms.mean:.{precision}f}",
             f"{self.total_ipc_travel_time_ms.standard_deviation:.{precision}f}",
             f"{self.total_ipc_travel_time_ms.min:.{precision}f}",
             f"{self.total_ipc_travel_time_ms.max:.{precision}f}"],
            ["Camera-to-Recorder Time",
             f"{total_stats.median:.{precision}f}",
             f"{total_stats.mean:.{precision}f}",
             f"{total_stats.standard_deviation:.{precision}f}",
             f"{total_stats.min:.{precision}f}",
             f"{total_stats.max:.{precision}f}"]
        ]

        summary_table = tabulate(
            summary_data,
            headers=["Metric", "Median (ms)", "Mean (ms)", "Std (ms)", "Min (ms)", "Max (ms)"],
            tablefmt="rst",
            floatfmt=f".{precision}f"  # This ensures decimal alignment
        )
        summary_section += summary_table

        # Combine all sections
        return header + timing_section + pipeline_section + summary_section
