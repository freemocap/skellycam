import logging
import os
from pathlib import Path
from typing import Dict, List, Union

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.diagnostics.framerate_diagnostics import gather_timestamps

logger = logging.getLogger(__name__)


def create_timestamp_diagnostic_plots(
    raw_frame_list_dictionary: Dict[str, List[FramePayload]],
    synchronized_frame_list_dictionary: Dict[str, List[FramePayload]],
    path_to_save_plots_png: Union[str, Path],
    open_image_after_saving: bool = False,
):
    """plot some diagnostics to assess quality of camera sync"""

    # opportunistic load of matplotlib to avoid startup time costs
    from matplotlib import pyplot as plt

    plt.set_loglevel("warning")

    synchronized_timestamps_dictionary = {}
    for (
        camera_id,
        camera_synchronized_frame_list,
    ) in synchronized_frame_list_dictionary.items():
        synchronized_timestamps_dictionary[camera_id] = (
            gather_timestamps(camera_synchronized_frame_list) / 1e9
        )

    raw_timestamps_dictionary = {}
    for camera_id, camera_raw_frame_list in raw_frame_list_dictionary.items():
        raw_timestamps_dictionary[camera_id] = (
            gather_timestamps(camera_raw_frame_list) / 1e9
        )

    max_frame_duration = 0.1
    fig = plt.figure(figsize=(18, 10))
    ax1 = plt.subplot(
        231,
        title="(Raw) Camera Frame Timestamp vs Frame#",
        xlabel="Frame#",
        ylabel="Timestamp (sec)",
    )
    ax2 = plt.subplot(
        232,
        ylim=(0, max_frame_duration),
        title="(Raw) Camera Frame Duration Trace",
        xlabel="Frame#",
        ylabel="Duration (sec)",
    )
    ax3 = plt.subplot(
        233,
        xlim=(0, max_frame_duration),
        title="(Raw) Camera Frame Duration Histogram (count)",
        xlabel="Duration(s, 1ms bins)",
        ylabel="Probability",
    )
    ax4 = plt.subplot(
        234,
        title="(Synchronized) Camera Frame Timestamp vs Frame#",
        xlabel="Frame#",
        ylabel="Timestamp (sec)",
    )
    ax5 = plt.subplot(
        235,
        ylim=(0, max_frame_duration),
        title="(Synchronized) Camera Frame Duration Trace",
        xlabel="Frame#",
        ylabel="Duration (sec)",
    )
    ax6 = plt.subplot(
        236,
        xlim=(0, max_frame_duration),
        title="(Synchronized) Camera Frame Duration Histogram (count)",
        xlabel="Duration(s, 1ms bins)",
        ylabel="Probability",
    )

    for camera_id, timestamps in raw_timestamps_dictionary.items():
        ax1.plot(timestamps, label=f"Camera# {str(camera_id)}")
        ax1.legend()
        ax2.plot(np.diff(timestamps), ".")
        ax3.hist(
            np.diff(timestamps),
            bins=np.arange(0, max_frame_duration, 0.0025),
            alpha=0.5,
        )

    for camera_id, timestamps in synchronized_timestamps_dictionary.items():
        ax4.plot(timestamps, label=f"Camera# {str(camera_id)}")
        ax4.legend()
        ax5.plot(np.diff(timestamps), ".")
        ax6.hist(
            np.diff(timestamps),
            bins=np.arange(0, max_frame_duration, 0.0025),
            alpha=0.5,
        )

    fig_save_path = Path(path_to_save_plots_png)
    plt.savefig(str(fig_save_path))
    logger.info(f"Saving diagnostic figure as png")

    if open_image_after_saving:
        os.startfile(path_to_save_plots_png, "open")
