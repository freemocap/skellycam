"""Tests for the PubSub IPC system — topic management, publish/subscribe, type safety."""
import queue
import time

import numpy as np
import pytest

from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.pubsub.pubsub_manager import (
    PubSubTopicManager,
    TopicTypes,
)
from skellycam.core.ipc.pubsub.pubsub_topics import (
    UpdateCamerasSettingsMessage,
    DeviceExtractedConfigMessage,
    RecordingInfoMessage,
    RecordingFinishedMessage,
    FramerateMessage,
    SetShmMessage,
)
from skellycam.core.camera.config.camera_config import CameraConfig, DEFAULT_CAMERA_ID
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.framerate_tracker import CurrentFramerate


# multiprocessing.Queue.put() hands data to a background feeder thread,
# so queue.empty() can race and return True immediately after put().
# Always use queue.get(timeout=...) instead of checking empty() first.
GET_TIMEOUT: float = 2.0


# ---------------------------------------------------------------------------
# PubSubTopicManager
# ---------------------------------------------------------------------------

class TestPubSubTopicManager:
    def test_has_all_topic_types(self) -> None:
        manager = PubSubTopicManager()
        for topic_type in TopicTypes:
            assert topic_type in manager.topics

    def test_subscribe_returns_queue(self) -> None:
        manager = PubSubTopicManager()
        sub = manager.get_subscription(TopicTypes.FRAMERATE)
        assert sub is not None
        assert hasattr(sub, "get")
        assert hasattr(sub, "put")

    def test_subscribe_unknown_topic_raises(self) -> None:
        manager = PubSubTopicManager()
        with pytest.raises(ValueError, match="Unknown topic"):
            manager.get_subscription("not_a_real_topic")  # type: ignore[arg-type]

    def test_close_clears_topics(self) -> None:
        manager = PubSubTopicManager()
        manager.get_subscription(TopicTypes.FRAMERATE)
        manager.close()
        assert len(manager.topics) == 0


# ---------------------------------------------------------------------------
# Publish / Subscribe Integration
# ---------------------------------------------------------------------------

class TestPubSubPublishSubscribe:
    def test_publish_delivers_to_subscriber(self) -> None:
        manager = PubSubTopicManager()
        sub = manager.get_subscription(TopicTypes.UPDATE_CAMERA_SETTINGS)

        configs = {DEFAULT_CAMERA_ID: CameraConfig()}
        msg = UpdateCamerasSettingsMessage(requested_configs=configs)
        manager.topics[TopicTypes.UPDATE_CAMERA_SETTINGS].publish(msg)

        # Use get(timeout=) instead of checking empty() — the feeder thread
        # may not have flushed the data to the pipe yet when empty() is called.
        received = sub.get(timeout=GET_TIMEOUT)
        assert isinstance(received, UpdateCamerasSettingsMessage)
        assert DEFAULT_CAMERA_ID in received.requested_configs

    def test_publish_delivers_to_multiple_subscribers(self) -> None:
        manager = PubSubTopicManager()
        sub1 = manager.get_subscription(TopicTypes.EXTRACTED_CONFIG)
        sub2 = manager.get_subscription(TopicTypes.EXTRACTED_CONFIG)

        config = CameraConfig(camera_id="test_cam", camera_index=0)
        msg = DeviceExtractedConfigMessage(extracted_config=config)
        manager.topics[TopicTypes.EXTRACTED_CONFIG].publish(msg)

        r1 = sub1.get(timeout=GET_TIMEOUT)
        r2 = sub2.get(timeout=GET_TIMEOUT)
        assert r1.extracted_config.camera_id == "test_cam"
        assert r2.extracted_config.camera_id == "test_cam"

    def test_publish_wrong_type_raises(self) -> None:
        manager = PubSubTopicManager()
        manager.get_subscription(TopicTypes.FRAMERATE)

        wrong_msg = UpdateCamerasSettingsMessage(
            requested_configs={DEFAULT_CAMERA_ID: CameraConfig()}
        )
        with pytest.raises(TypeError, match="Expected"):
            manager.topics[TopicTypes.FRAMERATE].publish(wrong_msg)

    def test_publish_overwrite_mode(self) -> None:
        manager = PubSubTopicManager()
        sub = manager.get_subscription(TopicTypes.RECORDING_INFO)

        msg1 = RecordingInfoMessage(recording_info=RecordingInfo.create_temp())
        msg2 = RecordingInfoMessage(recording_info=RecordingInfo.create_temp())

        # Publish msg1, then wait for it to actually land in the queue
        # before publishing msg2 with overwrite. Without this, the overwrite
        # drain loop (`while not sub.empty(): sub.get()`) may see an empty
        # queue because the feeder thread hasn't flushed msg1 yet.
        manager.topics[TopicTypes.RECORDING_INFO].publish(msg1)
        landed = sub.get(timeout=GET_TIMEOUT)
        assert landed.recording_info.recording_uuid == msg1.recording_info.recording_uuid
        # Put it back so the overwrite drain can find and remove it
        sub.put(landed)

        # Now publish with overwrite — drains msg1, then puts msg2
        manager.topics[TopicTypes.RECORDING_INFO].publish(msg2, overwrite=True)

        received = sub.get(timeout=GET_TIMEOUT)
        assert received.recording_info.recording_uuid == msg2.recording_info.recording_uuid

        # Confirm queue is now empty
        with pytest.raises(queue.Empty):
            sub.get(timeout=0.1)


# ---------------------------------------------------------------------------
# FramerateMessage
# ---------------------------------------------------------------------------

class TestFramerateMessage:
    def test_framerate_message_roundtrip(self) -> None:
        durations = np.array([33.0, 34.0, 33.5, 32.5, 33.0])
        fr = CurrentFramerate.from_durations_ms(
            durations_ms=durations,
            framerate_source="test",
        )
        msg = FramerateMessage(current_framerate=fr)
        assert msg.current_framerate.mean_frames_per_second > 0
        assert msg.current_framerate.framerate_source == "test"


# ---------------------------------------------------------------------------
# RecordingInfoMessage
# ---------------------------------------------------------------------------

class TestRecordingInfoMessage:
    def test_recording_info_message(self) -> None:
        info = RecordingInfo.create_temp()
        msg = RecordingInfoMessage(recording_info=info)
        assert msg.recording_info.recording_uuid == info.recording_uuid
