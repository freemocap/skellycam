from skellycam.core.types.timestamp_types import  TimestampStats


def generate_timestamps_stats_text_report(ts_stats: TimestampStats) -> str:
    """
    Generate a formatted text report from the statistics summary.

    Args:
        ts_stats: Dictionary of statistics summary

    Returns:
        Formatted text report
    """
    from tabulate import tabulate

    # Set precision for consistent decimal places
    precision = 3

    # Create timing table
    timing_data = [
        ["Framerate/FPS (Hz)",
         f"{ts_stats['framerate_stats']['median']:.{precision}f}",
         f"{ts_stats['framerate_stats']['mean']:.{precision}f}",
         f"{ts_stats['framerate_stats']['std']:.{precision}f}",
         f"{ts_stats['framerate_stats']['min']:.{precision}f}",
         f"{ts_stats['framerate_stats']['max']:.{precision}f}",
         ],
        ["Frame Duration (ms)",
         f"{ts_stats['frame_duration_stats']['median']:.{precision}f}",
         f"{ts_stats['frame_duration_stats']['mean']:.{precision}f}",
         f"{ts_stats['frame_duration_stats']['std']:.{precision}f}",
         f"{ts_stats['frame_duration_stats']['min']:.{precision}f}",
         f"{ts_stats['frame_duration_stats']['max']:.{precision}f}",
         ],
        ["Inter-Camera Frame Grab Sync (ms)",
         f"{ts_stats['inter_camera_grab_range_ms']['median']:.{precision}f}",
         f"{ts_stats['inter_camera_grab_range_ms']['mean']:.{precision}f}",
         f"{ts_stats['inter_camera_grab_range_ms']['std']:.{precision}f}",
         f"{ts_stats['inter_camera_grab_range_ms']['min']:.{precision}f}",
         f"{ts_stats['inter_camera_grab_range_ms']['max']:.{precision}f}",
         ]
    ]

    timing_table = tabulate(
        timing_data,
        headers=["Metric", "Median", "Mean", "Std", "Min", "Max"],
        tablefmt="rst",
        floatfmt=f".{precision}f"
    )

    # Create processing table data
    table_data = []

    # Add Camera Frame Acquisition stages
    acquisition_stages = [
        ("During frame grab", ts_stats['during_frame_grab_ms']),
        ("Idle before retrieve", ts_stats['idle_before_retrieve_ms']),
        ("During frame retrieve", ts_stats['during_frame_retrieve_ms']),
        ("Idle before copy to camera SHM", ts_stats['idle_before_copy_to_camera_shm_ms']),
        ("During copy to camera SHM", ts_stats['during_copy_to_camera_shm_ms']),
        ("Idle before frame record", ts_stats['idle_before_frame_record_ms']),
        ("During frame record", ts_stats['during_frame_record_ms']),
    ]

    # Calculate total time for percentage calculations
    total_time = ts_stats['total_camera_idle_time_ms']['mean']

    for stage_name, stats in acquisition_stages:
        percentage = (stats['mean'] / total_time) * 100 if total_time > 0 else 0
        table_data.append([
            stage_name,
            f"{stats['median']:.{precision}f}",
            f"{stats['mean']:.{precision}f}",
            f"{stats['std']:.{precision}f}",
            f"{stats['min']:.{precision}f}",
            f"{stats['max']:.{precision}f}",
            f"{percentage:.1f}%"
        ])

    # Add a separator line before the total
    table_data.append(["═" * 25, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 12, "═" * 10])

    # Add Total Processing Time with highlighting
    total_processing_stats = ts_stats['total_frame_processing_time_ms']
    processing_percentage = (total_processing_stats['mean'] / total_time) * 100 if total_time > 0 else 0
    table_data.append([
        "Total Frame Processing Time".upper(),
        f"{total_processing_stats['median']:.{precision}f}",
        f"{total_processing_stats['mean']:.{precision}f}",
        f"{total_processing_stats['std']:.{precision}f}",
        f"{total_processing_stats['min']:.{precision}f}",
        f"{total_processing_stats['max']:.{precision}f}",
        f"{processing_percentage:.1f}%"
    ])

    # Add Total Camera Idle Time
    total_idle_stats = ts_stats['total_camera_idle_time_ms']
    table_data.append([
        "Total Camera Idle Time".upper(),
        f"{total_idle_stats['median']:.{precision}f}",
        f"{total_idle_stats['mean']:.{precision}f}",
        f"{total_idle_stats['std']:.{precision}f}",
        f"{total_idle_stats['min']:.{precision}f}",
        f"{total_idle_stats['max']:.{precision}f}",
        f"{100 - processing_percentage:.1f}%"
    ])

    processing_table = tabulate(
        table_data,
        headers=["Stage", "Median (ms)", "Mean (ms)", "Std (ms)", "Min (ms)", "Max (ms)", "% of Total"],
        tablefmt="rst",
        floatfmt=f".{precision}f"
    )

    # Create the report
    report = f"""{'_' * 80}

Timestamp Statistics for recording: {ts_stats['recording_name']}

Number of Cameras: {ts_stats['number_of_cameras']}
Total Frames: {ts_stats['number_of_frames']}
Total Duration: {ts_stats['total_duration_sec']:.3f} seconds

FRAME TIMING STATISTICS
{timing_table}

FRAME PROCESSING TIMESTAMPS
{processing_table}

"""

    return report
