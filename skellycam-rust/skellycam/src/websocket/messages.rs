//! WebSocket JSON message types (server → client and client → server).
//! Uses serde for serialization. Message type strings match Python's
//! WebsocketMessageType enum exactly for frontend compatibility.

use serde::{Deserialize, Serialize};

/// All JSON message types sent over the WebSocket.
/// String values match Python's WebsocketMessageType exactly.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WebsocketMessageType {
    FramerateUpdate,
    AppState,
    PerformanceData,
    LogRecord,
}

/// Framerate update sent from server to client at ~4 Hz.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FramerateUpdateMessage {
    pub message_type: WebsocketMessageType,
    pub camera_group_identifier: String,
    pub backend_framerate: Option<CurrentFramerate>,
    pub frontend_framerate: Option<CurrentFramerate>,
}

/// Current framerate: median value over a recent window, plus frame count.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CurrentFramerate {
    pub framerate_source: String,
    pub median_framerate_hz: f64,
    pub number_of_observations: usize,
}

/// Message from the frontend acknowledging a rendered frame.
/// Used for cooperative backpressure over WebSocket.
#[derive(Debug, Clone, Deserialize)]
pub struct FrontendAcknowledgement {
    #[serde(rename = "frameNumber")]
    pub frame_number: i64,
    #[serde(rename = "displayImageSizes")]
    pub display_image_sizes: Option<serde_json::Value>,
}
