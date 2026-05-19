use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::Duration;

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::State;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;

use crate::api::application_state::AppState;

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
    let active_id = {
        state.active_group_id.lock().await.clone()
    };

    let Some(group_id) = active_id else {
        let _ = socket
            .send(Message::Text("no active camera group".into()))
            .await;
        return;
    };

    let mut last_frame_number: i64 = -1;

    loop {
        // Poll the active group's latest frontend payload
        let payload = {
            let manager = state.camera_manager.lock().await;
            manager
                .get_group(&group_id)
                .and_then(|g| g.latest_frontend_payload())
        };

        if let Some(payload) = payload {
            if payload.frame_number > last_frame_number {
                last_frame_number = payload.frame_number;
                if socket
                    .send(Message::Binary(payload.jpeg_bytes.into()))
                    .await
                    .is_err()
                {
                    break;
                }
            }
        }

        // Check shutdown flag
        if state.shutdown_flag.load(Ordering::SeqCst) {
            break;
        }

        // ~10ms poll interval (~100 Hz max relay rate)
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}
