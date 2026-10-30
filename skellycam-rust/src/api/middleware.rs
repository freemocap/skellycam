//! HTTP request/response logging middleware.
//!
//! Prints one line per request and one per response. Request bodies are
//! captured and shown (truncated to 256 bytes). Response bodies are never
//! captured — their content-type and byte count are logged instead.

use axum::extract::Request;
use axum::middleware::Next;
use axum::response::Response;
use std::time::Instant;

const MAX_BODY_DISPLAY: usize = 256;

pub async fn log_requests(request: Request, next: Next) -> Response {
    let method = request.method().clone();
    let uri = request.uri().clone();
    let path = uri.path().to_string();
    let query = uri.query().unwrap_or("");

    // Capture request body (up to 1 MB buffer, only show first 256 bytes)
    let (parts, body) = request.into_parts();
    let body_bytes = axum::body::to_bytes(body, 1024 * 1024)
        .await
        .unwrap_or_default();

    let query_suffix = if query.is_empty() {
        String::new()
    } else {
        format!("?{query}")
    };

    // ── Request line ──
    if body_bytes.is_empty() {
        eprintln!("→  {method} {path}{query_suffix}");
    } else {
        let body_str = String::from_utf8_lossy(&body_bytes);
        let body_display = truncate_str(&body_str, MAX_BODY_DISPLAY);
        eprintln!("→  {method} {path}{query_suffix}  |  {body_display}");
    }

    // Reconstruct request with the buffered body
    let request = Request::from_parts(parts, axum::body::Body::from(body_bytes));

    let start = Instant::now();
    let response = next.run(request).await;
    let elapsed = start.elapsed();

    // ── Response line ──
    let status = response.status();
    let status_emoji = if status.is_success() {
        ""
    } else if status.is_server_error() {
        "  ERROR"
    } else if status.is_client_error() {
        ""
    } else {
        ""
    };

    let content_type = response
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    let body_hint = if status.as_u16() == 101 {
        "[websocket upgrade]".to_string()
    } else if let Some(len) = response
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.parse::<u64>().ok())
    {
        format!("[{len}b {content_type}]")
    } else if content_type.is_empty() {
        String::new()
    } else {
        format!("[{content_type}]")
    };

    eprintln!(
        "←  {status}{status_emoji}  {method} {path}{query_suffix}  ({elapsed:.2?})  {body_hint}"
    );

    response
}

fn truncate_str(s: &str, max_len: usize) -> String {
    let s = s.trim();
    if s.len() <= max_len {
        return s.to_string();
    }
    let mut end = max_len;
    while !s.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}… ({}b total)", &s[..end], s.len())
}
