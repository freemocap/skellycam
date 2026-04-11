"""Tests for the device and camera-group router endpoints."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from skellycam.core.camera.config.camera_config import CameraConfig, DEFAULT_CAMERA_ID
from skellycam.core.device_detection.detect_cameras_devices import CameraDeviceInfo


class TestDetectCameras:
    def test_detect_cameras_returns_list(self, client):
        """GET /devices/cameras returns detected cameras."""
        mock_camera = CameraDeviceInfo(
            index=0,
            name="Test Camera",
            vendor_id=1234,
            product_id=5678,
            path="/dev/video0",
            backend_id=200,
            backend_name="V4L2",
        )

        with patch(
            "skellycam.api.http.devices.devices_router.detect_available_cameras",
            return_value=[mock_camera],
        ):
            response = client.get("/devices/cameras")
        assert response.status_code == 200
        data = response.json()
        assert "cameras" in data
        assert len(data["cameras"]) == 1

    def test_detect_cameras_empty(self, client):
        """GET /devices/cameras returns empty list when no cameras."""
        with patch(
            "skellycam.api.http.devices.devices_router.detect_available_cameras",
            return_value=[],
        ):
            response = client.get("/devices/cameras")
        assert response.status_code == 200
        data = response.json()
        assert data["cameras"] == []

    def test_detect_cameras_error(self, client):
        """GET /devices/cameras returns 500 on detection error."""
        with patch(
            "skellycam.api.http.devices.devices_router.detect_available_cameras",
            side_effect=RuntimeError("Camera detection failed"),
        ):
            response = client.get("/devices/cameras")
        assert response.status_code == 500


class TestCameraGroupApply:
    def test_apply_creates_group(self, client, mock_camera_group_manager):
        """PUT /camera-group creates a camera group."""
        mock_group = MagicMock()
        mock_group.id = "group-0"
        mock_group.configs = {DEFAULT_CAMERA_ID: CameraConfig()}
        mock_state = MagicMock()
        mock_state.id = "group-0"
        mock_state.configs = {DEFAULT_CAMERA_ID: CameraConfig()}
        mock_state.cameras = {}
        mock_state.alive = True
        mock_group.to_state.return_value = mock_state
        mock_camera_group_manager.create_or_update_camera_group = AsyncMock(
            return_value=mock_group
        )

        response = client.put(
            "/camera-group",
            json={"camera_configs": {DEFAULT_CAMERA_ID: CameraConfig().model_dump()}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["group_id"] == "group-0"
        assert DEFAULT_CAMERA_ID in data["camera_configs"]

    def test_apply_error(self, client, mock_camera_group_manager):
        """PUT /camera-group returns 500 on error."""
        mock_camera_group_manager.create_or_update_camera_group = AsyncMock(
            side_effect=RuntimeError("Something went wrong")
        )
        response = client.put(
            "/camera-group",
            json={"camera_configs": {DEFAULT_CAMERA_ID: CameraConfig().model_dump()}},
        )
        assert response.status_code == 500


class TestCameraGroupManagement:
    def test_get_camera_group(self, client, mock_camera_group_manager):
        """GET /camera-group returns current state."""
        response = client.get("/camera-group")
        assert response.status_code == 200

    def test_delete_camera_group(self, client, mock_camera_group_manager):
        """DELETE /camera-group tears down camera group."""
        response = client.request("DELETE", "/camera-group")
        assert response.status_code == 204
