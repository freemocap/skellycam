//! HTTP request/response logging middleware.
//!
//! Prints every incoming request and outgoing response as formatted,
//! indented JSON to stderr. Request bodies are buffered and logged;
//! response bodies are logged on success. WebSocket upgrade requests
//! are logged but body capture is skipped (no response body to log).

use axum::extract::Request;
use axum::middleware::Next;
use axum::response::Response;
use std::time::Instant;

pub async fn log_requests(request: Request, next: Next) -> Response {
    let method = request.method().clone();
    let uri = request.uri().clone();
    let path = uri.path().to_string();
    let query = uri.query().unwrap_or("");

    // Buffer the request body so we can log it
    let (parts, body) = request.into_parts();
    let body_bytes = axum::body::to_bytes(body, 1024 * 1024)
        .await
        .unwrap_or_default();

    // ── Log request ──
    let body_str = String::from_utf8_lossy(&body_bytes);
    let pretty_body = format_json_or_raw(&body_str);

    let query_suffix = if query.is_empty() {
        String::new()
    } else {
        format!("?{query}")
    };

    eprintln!();
    eprintln!("╔══════════════════════════ REQUEST ══════════════════════════");
    eprintln!("║  {method} {path}{query_suffix}");
    eprintln!("╠══════════════════════════ BODY ═════════════════════════════");
    for line in pretty_body.lines() {
        eprintln!("║  {line}");
    }
    eprintln!("╚══════════════════════════════════════════════════════════════");

    // Reconstruct request with the buffered body
    let request = Request::from_parts(parts, axum::body::Body::from(body_bytes));

    let start = Instant::now();
    let response = next.run(request).await;
    let elapsed = start.elapsed();

    // ── Log response ──
    let status = response.status();
    let status_str = if status.is_success() {
        format!("{status}")
    } else if status.is_server_error() {
        format!("{status}  ← SERVER ERROR")
    } else if status.is_client_error() {
        format!("{status}  ← CLIENT ERROR")
    } else {
        format!("{status}")
    };

    // Buffer response body for logging (only for non-WebSocket, non-streaming)
    let content_type = response
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    let is_json = content_type.contains("json");
    let is_websocket = status.as_u16() == 101;

    eprintln!();
    eprintln!("╔══════════════════════════ RESPONSE ═════════════════════════");
    eprintln!("║  {status_str}  ({elapsed:.2?})");
    if !is_websocket {
        eprintln!("╠══════════════════════════ BODY ═════════════════════════════");
        if is_json {
            let (parts, body) = response.into_parts();
            let body_bytes = axum::body::to_bytes(body, 1024 * 1024)
                .await
                .unwrap_or_default();
            let body_str = String::from_utf8_lossy(&body_bytes);
            let pretty_body = format_json_or_raw(&body_str);
            for line in pretty_body.lines() {
                eprintln!("║  {line}");
            }
            eprintln!("╚══════════════════════════════════════════════════════════════");
            return Response::from_parts(parts, axum::body::Body::from(body_bytes));
        }
    }
    eprintln!("╚══════════════════════════════════════════════════════════════");

    response
}

/// Try to format a string as pretty-printed JSON. If it's not valid JSON,
/// return the raw string (trimmed).
fn format_json_or_raw(s: &str) -> String {
    let s = s.trim();
    if s.is_empty() {
        return "(empty body)".to_string();
    }
    match serde_json::from_str::<serde_json::Value>(s) {
        Ok(value) => serde_json::to_string_pretty(&value).unwrap_or_else(|_| s.to_string()),
        Err(_) => {
            // Truncate very long non-JSON bodies
            if s.len() > 500 {
                format!("{}... ({} bytes total, truncated)", &s[..500], s.len())
            } else {
                s.to_string()
            }
        }
    }
}
