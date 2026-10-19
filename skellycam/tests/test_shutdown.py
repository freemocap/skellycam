"""Tests for the shutdown endpoint."""
from unittest.mock import patch
import logging


class TestShutdownEndpoint:
    def test_shutdown_returns_json(self, client, mock_global_kill_flag, monkeypatch):
        """GET /shutdown triggers shutdown and returns JSON response."""
        monkeypatch.setattr(logging.Logger, "api", logging.Logger.info, raising=False)
        with patch("os.kill") as mock_kill:
            response = client.get("/shutdown")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shutdown_initiated"
        assert "message" in data
        assert mock_global_kill_flag.value
        # The worker monitor owns final termination after saves complete.
        mock_kill.assert_not_called()
