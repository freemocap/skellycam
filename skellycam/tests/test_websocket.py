"""Tests for the WebSocket connect endpoint and basic protocol."""
import json

import pytest


@pytest.mark.timeout(10)
class TestWebsocketConnect:
    def test_websocket_connect_disconnect(self, client):
        """Can connect to the websocket endpoint and cleanly disconnect."""
        with client.websocket_connect("/skellycam/websocket/connect") as ws:
            # If we get here, the connection was accepted
            ws.close()

    def test_websocket_ping_pong(self, client):
        """Sending 'ping' text should receive 'pong' back."""
        with client.websocket_connect("/skellycam/websocket/connect") as ws:
            ws.send_text("ping")
            
            # Use a loop to skip app_state messages
            for _ in range(5):  # Try a few times
                response = ws.receive_text()
                try:
                    data = json.loads(response)
                    if isinstance(data, dict) and data.get("message_type") in ("app_state", "framerate_update"):
                        continue
                except json.JSONDecodeError:
                    pass
                
                assert response == "pong"
                break
            else:
                pytest.fail("Did not receive pong response")

    def test_websocket_receives_app_state(self, client):
        """After connecting, server should send an app_state JSON message."""
        with client.websocket_connect("/skellycam/websocket/connect") as ws:
            data = ws.receive_json(mode="text")
            assert data["message_type"] == "app_state"
            assert data["state"] == {"camera_groups": {}}
            assert data["server_pid"] > 0

    def test_websocket_frame_acknowledgment(self, client, mock_camera_group_manager):
        """Sending a frame acknowledgment JSON updates the server state."""
        with client.websocket_connect("/skellycam/websocket/connect") as ws:
            ack_message = json.dumps({
                "frameNumber": 42,
                "displayImageSizes": None,
            })
            ws.send_text(ack_message)
            # Send a ping to verify connection is still alive after the ack
            ws.send_text("ping")
            
            # Loop to skip app_state messages
            for _ in range(5):
                response = ws.receive_text()
                try:
                    data = json.loads(response)
                    if isinstance(data, dict) and data.get("message_type") in ("app_state", "framerate_update"):
                        continue
                except json.JSONDecodeError:
                    pass
                    
                assert response == "pong"
                break
            else:
                pytest.fail("Did not receive pong response")
