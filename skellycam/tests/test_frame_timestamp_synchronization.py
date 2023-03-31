import logging

import numpy as np

logger = logging.getLogger(__name__)


def test_frame_timestamp_synchronization(synchronized_frame_list_dictionary):
    frame_count_list = []

    for frame_list in synchronized_frame_list_dictionary.values():
        frame_count_list.append(len(frame_list))

    logger.info(f"frame_count_list: {frame_count_list}")

    assert np.all(
        np.diff(frame_count_list) == 0
    ), "Frame count is not the same for all cameras"

    logger.info("Test passed: Frame count is the same for all cameras :D")
