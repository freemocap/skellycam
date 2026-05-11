//! Centralized error handling for HTTP endpoints.
//! Converts anyhow errors into JSON 500 responses matching Python's format.

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

/// Application error type — wraps anyhow errors for HTTP responses.
#[derive(Debug)]
pub struct ApplicationError(pub anyhow::Error);

impl IntoResponse for ApplicationError {
    fn into_response(self) -> Response {
        let body = json!({
            "detail": format!("{:#}", self.0),
        });
        (StatusCode::INTERNAL_SERVER_ERROR, Json(body)).into_response()
    }
}

impl<E: Into<anyhow::Error>> From<E> for ApplicationError {
    fn from(error: E) -> Self {
        Self(error.into())
    }
}
