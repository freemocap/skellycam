//! WebSocket server: 4 concurrent tasks per connection.
//! Image relay (binary), log relay (JSON), state sender (JSON, 1s interval),
//! client message handler (backpressure acks, display sizes, ping/pong).

pub struct WebSocketServer {}

impl WebSocketServer {
    pub fn new() -> Self {
        Self {}
    }
}
