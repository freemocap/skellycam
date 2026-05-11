//! SkellyCam — synchronized multi-camera recording and streaming.
//!
//! Rust backend replacing the Python FastAPI + OpenCV + multiprocessing stack.
//! Preserves the HTTP API and WebSocket binary protocol for frontend compatibility.

pub mod camera;
pub mod camera_group;
pub mod camera_group_manager;
pub mod recording;
pub mod timestamps;
pub mod websocket;
pub mod api;
pub mod frontend_payload;
