import logging
from typing import List, Dict

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


def test_frame_counts_equal(frame_lists: Dict[str, List[FramePayload]]):
    frame_count_list = []

    for frame_list in frame_lists.values():
        frame_count_list.append(len(frame_list))

    logger.info(f"frame_count_list: {frame_count_list}")

    assert np.all(
        np.diff(frame_count_list) == 0
    ), "Frame count is not the same for all cameras"

    logger.info("Test passed: Frame count is the same for all cameras :D")

    return True
