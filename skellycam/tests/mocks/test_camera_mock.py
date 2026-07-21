import time
import cv2
import pytest
import numpy as np

from skellycam.tests.mocks.camera_mock import MockVideoCapture

class TestMockVideoCapture:
    def test_initialization(self):
        """Verify mock initializes with defaults and is opened."""
        cap = MockVideoCapture()
        assert cap.isOpened()
        assert cap.get(cv2.CAP_PROP_FPS) == 30.0
        assert cap.get(cv2.CAP_PROP_FRAME_WIDTH) == 640.0
        assert cap.get(cv2.CAP_PROP_FRAME_HEIGHT) == 480.0
        cap.release()
        assert not cap.isOpened()

    def test_blocking_behavior(self):
        """Verify the read() method blocks to maintain FPS."""
        # Using a higher FPS for faster test, but low enough to notice blocking
        fps = 60.0
        cap = MockVideoCapture()
        cap.set(cv2.CAP_PROP_FPS, fps)
        
        num_frames = 10
        start_time = time.time()
        for _ in range(num_frames):
            ret, frame = cap.read()
            assert ret
            assert frame is not None
        end_time = time.time()
        
        elapsed = end_time - start_time
        expected_duration = num_frames / fps
        
        # Allow some small overhead, but it should be at least the expected duration
        assert elapsed >= expected_duration * 0.95 
        # Also shouldn't take too much longer (e.g., 20% overhead max)
        assert elapsed <= expected_duration * 1.5

        cap.release()

    def test_frame_content(self):
        """Verify the frame contains expected data and overlays."""
        cap = MockVideoCapture()
        ret, frame = cap.read()
        
        assert ret
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (480, 640, 3)
        assert frame.dtype == np.uint8
        
        # Check if the frame is not completely black (should have text)
        assert np.sum(frame) > 0
        cap.release()

    def test_set_get_configuration(self):
        """Verify setting and getting properties."""
        cap = MockVideoCapture()
        
        # Test valid FPS
        assert cap.set(cv2.CAP_PROP_FPS, 60.0)
        assert cap.get(cv2.CAP_PROP_FPS) == 60.0
        
        # Test valid Resolution
        assert cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        assert cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        assert cap.get(cv2.CAP_PROP_FRAME_WIDTH) == 1920
        assert cap.get(cv2.CAP_PROP_FRAME_HEIGHT) == 1080
        
        # Test Exposure
        assert cap.set(cv2.CAP_PROP_EXPOSURE, -10.0)
        assert cap.get(cv2.CAP_PROP_EXPOSURE) == -10.0
        
        cap.release()

    def test_invalid_configuration(self):
        """Verify error handling for invalid configurations."""
        cap = MockVideoCapture()
        
        # Invalid FPS
        assert not cap.set(cv2.CAP_PROP_FPS, 1000.0)  # Too high
        assert not cap.set(cv2.CAP_PROP_FPS, -1.0)    # Negative
        assert cap.get(cv2.CAP_PROP_FPS) == 30.0      # Should remain default

        # Invalid Width
        assert not cap.set(cv2.CAP_PROP_FRAME_WIDTH, 10000.0)
        assert not cap.set(cv2.CAP_PROP_FRAME_WIDTH, 0.0)
        assert cap.get(cv2.CAP_PROP_FRAME_WIDTH) == 640.0

        # Invalid Height
        assert not cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 5000.0)
        assert not cap.set(cv2.CAP_PROP_FRAME_HEIGHT, -100.0)
        assert cap.get(cv2.CAP_PROP_FRAME_HEIGHT) == 480.0
        
        cap.release()

    def test_read_after_release(self):
        """Verify read() fails after release."""
        cap = MockVideoCapture()
        cap.release()
        ret, frame = cap.read()
        assert not ret
        assert frame is None
