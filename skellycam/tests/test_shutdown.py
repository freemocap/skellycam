"""Tests for the shutdown endpoint."""
from unittest.mock import patch

import pytest


class TestShutdownEndpoint:
    def test_shutdown_returns_json(self, client):
        """GET /shutdown triggers shutdown and returns JSON response."""
        with patch("skellycam.api.http.app.shutdown.os.kill") as mock_kill:
            response = client.get("/shutdown")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shutdown_initiated"
        assert "message" in data
        # Verify os.kill was called (to send SIGTERM)
        mock_kill.assert_called_once()
