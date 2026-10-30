use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::State;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;

use crate::api::application_state::AppState;
use crate::websocket::framerate_tracker::{FramerateTracker, FramerateUpdateMessage};
use crate::websocket::log_relay;

const POLL_INTERVAL_MS: u64 = 10;
const FRAMERATE_SEND_INTERVAL_MS: u64 = 250;

pub fn websocket_route() -> Router<Arc<AppState>> {
    Router::new().route(
        "/skellycam/websocket/connect",
        get(websocket_handler),
    )
}

async fn websocket_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(mut socket: WebSocket, state: Arc<AppState>) {
    let mut last_group_id: Option<String> = None;
    let mut last_frame_number: i64 = -1;

    let mut backend_tracker = FramerateTracker::new("Server");
    let mut frontend_tracker = FramerateTracker::new("Display");
    let mut last_frontend_send: Option<Instant> = None;
    let mut last_framerate_report = Instant::now();
    let mut last_camera_fps: Option<f64> = None;

    // ── Log relay: bridge broadcast → mpsc for non-blocking drain ──
    let (log_tx, mut log_rx) = tokio::sync::mpsc::channel::<String>(256);
    if let Some(mut broadcast_rx) = log_relay::subscribe() {
        tokio::spawn(async move {
            loop {
                match broadcast_rx.recv().await {
                    Ok(msg) => {
                        if log_tx.send(msg).await.is_err() {
                            break; // receiver dropped
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {
                        continue;
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                }
            }
        });
    }

    loop {
        // ── Which group is currently active? ──
        let active_id = {
            state.active_group_id.lock().await.clone()
        };

        if active_id != last_group_id {
            last_group_id = active_id.clone();
            last_frame_number = -1;
        }

        // ── Poll for a new frame (if a group is active) ──
        if let Some(ref group_id) = active_id {
            let payload = {
                let manager = state.camera_manager.lock().await;
                manager
                    .get_group(group_id)
                    .and_then(|g| g.latest_frontend_payload())
            };

            if let Some(payload) = payload {
                if payload.frame_number > last_frame_number {
                    backend_tracker.record_backend_frame(
                        payload.timestamp_ns,
                        payload.frame_number,
                    );
                    last_frame_number = payload.frame_number;
                    if payload.camera_fps > 0.0 {
                        last_camera_fps = Some(payload.camera_fps);
                    }

                    let now = Instant::now();
                    if let Some(prev) = last_frontend_send {
                        let duration_ms = now.duration_since(prev).as_secs_f64() * 1000.0;
                        frontend_tracker.record_frontend_frame(duration_ms);
                    }
                    last_frontend_send = Some(now);

                    if socket
                        .send(Message::Binary(payload.jpeg_bytes.into()))
                        .await
                        .is_err()
                    {
                        break;
                    }
                }
            }

            // ── Send framerate update at ~4 Hz ──
            if last_framerate_report.elapsed()
                >= Duration::from_millis(FRAMERATE_SEND_INTERVAL_MS)
            {
                let message = FramerateUpdateMessage {
                    message_type: "framerate_update".to_string(),
                    camera_group_id: group_id.clone(),
                    backend_framerate: backend_tracker.snapshot_and_reset(),
                    frontend_framerate: frontend_tracker.snapshot_and_reset(),
                    camera_fps: last_camera_fps,
                };
                if let Ok(json) = serde_json::to_string(&message) {
                    if socket.send(Message::Text(json.into())).await.is_err() {
                        break;
                    }
                }
                last_framerate_report = Instant::now();
            }
        }

        // ── Drain pending log messages (non-blocking) ──
        while let Ok(msg) = log_rx.try_recv() {
            if socket.send(Message::Text(msg.into())).await.is_err() {
                return; // client disconnected
            }
        }

        if state.shutdown_flag.load(Ordering::SeqCst) {
            break;
        }

        tokio::time::sleep(Duration::from_millis(POLL_INTERVAL_MS)).await;
    }
}
