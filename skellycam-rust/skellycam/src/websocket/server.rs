//! WebSocket server: relays JPEG-encoded frontend payloads to connected browsers.

use std::sync::Arc;

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::State;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;
use tokio::sync::broadcast;

use crate::api::application_state::AppState;

pub fn websocket_route() -> Router<Arc<AppState>> {
    Router::new().route("/skellycam/websocket/connect", get(websocket_handler))
}

async fn websocket_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(mut socket: WebSocket, state: Arc<AppState>) {
    // Subscribe to the frame broadcast
    let rx = {
        let guard = state.frame_broadcast.lock().await;
        guard.as_ref().map(|tx| tx.subscribe())
    };

    let Some(mut rx) = rx else {
        let _ = socket
            .send(Message::Text("no active camera group".into()))
            .await;
        return;
    };

    // Forward broadcast frames to the WebSocket client
    loop {
        match rx.recv().await {
            Ok(binary) => {
                if socket.send(Message::Binary(binary.into())).await.is_err() {
                    break;
                }
            }
            Err(broadcast::error::RecvError::Lagged(n)) => {
                eprintln!("[ws] client lagged by {n} frames");
                continue;
            }
            Err(broadcast::error::RecvError::Closed) => {
                break;
            }
        }
    }
}
