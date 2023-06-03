import csv
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Union

import numpy as np

logger = logging.getLogger(__name__)

TIMESTAMP_COLUMN_NAMES = ["frame_number",
                          "timestamp_ns_from_recording_start",
                          "timestamp_sec_from_recording_start",
                          "frame_duration_ns",
                          "frame_duration_sec",
                          "frames_per_second_mean",
                          "frames_per_second_std",
                          "timestamp_local",
                          "timestamp_utc",
                          "unix_epoch_time"]


def get_timestamp_csv_header():
    return ",".join(TIMESTAMP_COLUMN_NAMES)


TIMESTAMP_VARIABILITY_THRESHOLD = 0.5  # we'll return the framerate if the std is less than 10% of the mean
DOUBLE_CHECK_THRESHOLD = 10  # we'll return the framerate after variability is below threshold for this many frames


class TimestampManager:
    """
    This class is responsible for managing the timestamps streaming from a single camera.
    it calculates frame_rate, and saves the timestamps to a csv file.
    """

    def __init__(self,
                 timestamp_file_save_path: Union[str, Path] = None):

        self._recording_start_datetime = None
        self._double_check_count = 0
        self._timestamps = []
        self._previous_timestamp_ns = None

        self._initial_frames_per_second = None

        self._timestamp_file_path = timestamp_file_save_path
        self._timestamp_csv_writer = self._initialize_timestamp_csv()

    def receive_new_timestamp(self, timestamp_ns: int) -> Union[float, None]:
        """
        Receives a new timestamp from the camera, and returns the framerate if we have a reliable enough (else returns None).
        """
        try:
            #first frame stuff
            if self._previous_timestamp_ns is None:
                self._previous_timestamp_ns = timestamp_ns
            if self._recording_start_datetime is None:
                self._recording_start_datetime = datetime.now()

            self._timestamps.append(timestamp_ns)
            self._add_timestamp_to_csv(timestamp_ns)

            self._previous_timestamp_ns = timestamp_ns
            return True
        except Exception as e:
            logger.error(f"Error receiving new timestamp: {e}")
            logger.error(traceback.format_exc())


    def estimate_framerate(self, ):
        try:
            if len(self._timestamps) > 1:
                return self._calc_frames_per_second_mean()
        except Exception as e:
            logger.error(f"Error estimating framerate: {e}")
            logger.error(traceback.format_exc())


    def _calc_frames_per_second_std(self):
        frame_durations = np.diff(self._timestamps) / 1e9  # convert to seconds
        frames_per_second = 1 / frame_durations
        return np.std(frames_per_second)

    def _calc_frames_per_second_mean(self):
        frame_durations = np.diff(self._timestamps) / 1e9  # convert to seconds
        frames_per_second = 1 / frame_durations
        return np.mean(frames_per_second)

    def _initialize_timestamp_csv(self):
        Path(self._timestamp_file_path).touch(exist_ok=True)
        file = open(self._timestamp_file_path, 'w')
        writer = csv.writer(file)
        writer.writerow(get_timestamp_csv_header())
        return writer

    def close(self):
        self._timestamp_csv_writer.close()

    def _add_timestamp_to_csv(self, timestamp_ns):
        row_data = [len(self._timestamps),
                    timestamp_ns,
                    timestamp_ns / 1e9,
                    timestamp_ns - self._previous_timestamp_ns,
                    (timestamp_ns - self._previous_timestamp_ns) / 1e9,
                    self._calc_frames_per_second_mean(),
                    self._calc_frames_per_second_std(),
                    self._get_local_timestamp(timestamp_ns),
                    0,  # TODO - add utc timestamp
                    0,  # TODO - add unix epoch time
                    ]
        csv_row = ",".join([str(x) for x in row_data])
        self._timestamp_csv_writer.writerow(csv_row)

    def _get_local_timestamp(self, timestamp_ns):
        return (self._recording_start_datetime + timedelta(timestamp_ns / 1e9)).isoformat()

