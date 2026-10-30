//! Log-relay layer that forwards `tracing` events to the frontend via
//! WebSocket, producing JSON identical to Python's `skellylogs.LogRecordModel`.
//!
//! Architecture:
//! ```text
//! tracing event (any thread)
//!     |
//!     v
//! LogRelayLayer::on_event()      ←  runs on caller's thread (same as Python's
//!     |  builds JSON,                QueueHandler.emit())
//!     |  broadcast::send()           non-blocking push
//!     v
//! broadcast::channel<String>     ←  pre-serialized JSON strings
//!     |
//!     v
//! log_relay_task() in server.rs  ←  reads channel, sends over WebSocket
//!     |
//!     v
//! frontend LogStore.add()
//! ```
//!
//! The frontend validates payloads via Zod's `LogRecordSchema` (see
//! `skellycam-ui/src/services/server/server-helpers/log-store.ts`) and
//! dispatches on `message_type === "log_record"`.

use std::fmt;
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

use chrono::Local;
use tokio::sync::broadcast;
use tracing::Subscriber;
use tracing_subscriber::layer::Context;
use tracing_subscriber::Layer;

// ---------------------------------------------------------------------------
// Global broadcast channel
// ---------------------------------------------------------------------------

/// Global sender for the log-relay broadcast channel.
///
/// Set once during `init_logging()` and never reset.  Each WebSocket
/// connection calls [`subscribe`] to get its own receiver.
static LOG_SENDER: OnceLock<broadcast::Sender<String>> = OnceLock::new();

/// Backlog in messages.  When the channel is full, the oldest message is
/// dropped (analogous to Python's `maxsize=1000` queue with `put_nowait`).
const CHANNEL_CAPACITY: usize = 256;

/// Initialise the broadcast channel.  Must be called before any tracing
/// events fire (i.e. inside [`crate::init_logging`]).
pub fn init_log_relay() {
    let (tx, _rx) = broadcast::channel(CHANNEL_CAPACITY);
    LOG_SENDER.set(tx).ok(); // ok if already set (idempotent via try_init)
}

/// Return a fresh receiver for a new WebSocket connection.
pub fn subscribe() -> Option<broadcast::Receiver<String>> {
    LOG_SENDER.get().map(|tx| tx.subscribe())
}

/// Return the global sender, if initialised.
fn sender() -> Option<&'static broadcast::Sender<String>> {
    LOG_SENDER.get()
}

// ---------------------------------------------------------------------------
// Visitor — extracts a human-readable "message" string from tracing fields
// ---------------------------------------------------------------------------

/// Walks the key-value fields attached to a `tracing::Event` and builds a
/// display string matching what `tracing_subscriber::fmt::format::Full` would
/// produce for the *message portion only* (no metadata / level / timestamp).
///
/// Example input:
/// ```text
/// tracing::info!(camera_id = "cam-0", "frame captured")
/// ```
/// Produces: `"frame captured camera_id=cam-0"`
struct MessageVisitor {
    result: String,
    have_message: bool,
}

impl MessageVisitor {
    fn push(&mut self, name: &str, value: &str) {
        if name == "message" {
            // The literal format-string argument always comes first.
            if self.have_message {
                self.result = format!("{value} {}", self.result);
            } else {
                self.result = value.to_string();
                self.have_message = true;
            }
        } else {
            let pair = format!("{name}={value}");
            if self.have_message {
                self.result.push(' ');
                self.result.push_str(&pair);
            } else {
                self.result = pair;
                self.have_message = true;
            }
        }
    }
}

impl tracing::field::Visit for MessageVisitor {
    fn record_debug(&mut self, field: &tracing::field::Field, value: &dyn fmt::Debug) {
        let s = format!("{value:?}");
        // Strip surrounding quotes from Display-formatted strings.
        let s = s.strip_prefix('"').unwrap_or(&s);
        let s = s.strip_suffix('"').unwrap_or(s);
        self.push(field.name(), s);
    }

    fn record_str(&mut self, field: &tracing::field::Field, value: &str) {
        self.push(field.name(), value);
    }

    // record_f64 and record_i64 delegate to record_debug so all numeric
    // fields are captured without needing per-type handlers.

    fn record_f64(&mut self, field: &tracing::field::Field, value: f64) {
        self.push(field.name(), &format!("{value}"));
    }

    fn record_i64(&mut self, field: &tracing::field::Field, value: i64) {
        self.push(field.name(), &format!("{value}"));
    }

    fn record_u64(&mut self, field: &tracing::field::Field, value: u64) {
        self.push(field.name(), &format!("{value}"));
    }

    fn record_bool(&mut self, field: &tracing::field::Field, value: bool) {
        self.push(field.name(), &format!("{value}"));
    }
}

// ---------------------------------------------------------------------------
// Layer
// ---------------------------------------------------------------------------

/// A `tracing_subscriber::Layer` that formats every event as a JSON
/// `LogRecordModel` dict and pushes it onto the global broadcast channel.
///
/// The JSON is **identical** to what Python's
/// `skellylogs.handlers.WebSocketQueueHandler` produces, so the SkellyCam
/// frontend `LogStore` can ingest Rust-emitted logs without any changes.
pub struct LogRelayLayer {
    start_time: Instant,
    prev_time: Mutex<Instant>,
    process_name: String,
}

impl LogRelayLayer {
    pub fn new() -> Self {
        let process_name = std::env::current_exe()
            .ok()
            .and_then(|p| p.file_stem()?.to_str().map(String::from))
            .unwrap_or_else(|| "unknown".to_string());

        Self {
            start_time: Instant::now(),
            prev_time: Mutex::new(Instant::now()),
            process_name,
        }
    }
}

impl<S> Layer<S> for LogRelayLayer
where
    S: Subscriber,
{
    fn on_event(&self, event: &tracing::Event<'_>, _ctx: Context<'_, S>) {
        let sender = match sender() {
            Some(s) => s,
            None => return,
        };

        // Zero receivers → no WebSocket connected.  Skip serialisation
        // entirely to avoid wasting CPU in the hot camera loop.
        if sender.receiver_count() == 0 {
            return;
        }

        let metadata = event.metadata();
        let target = metadata.target();

        // ── Message string ──────────────────────────────────────
        let mut visitor = MessageVisitor {
            result: String::new(),
            have_message: false,
        };
        event.record(&mut visitor);
        let plain_message = visitor.result;

        // ── Timestamp & delta ────────────────────────────────────
        let now = Instant::now();
        let ts = Local::now();

        let delta_ms = {
            let mut prev = self.prev_time.lock().unwrap();
            let delta = now.duration_since(*prev);
            *prev = now;
            format!("{:.3}ms", delta.as_secs_f64() * 1000.0)
        };

        // ── Thread identity ─────────────────────────────────────
        let current_thread = std::thread::current();
        let tid_raw = format!("{:?}", current_thread.id());
        let tid = tid_raw
            .trim_start_matches("ThreadId(")
            .trim_end_matches(')');
        let tname = current_thread.name().unwrap_or("unnamed");

        // ── Location ────────────────────────────────────────────
        let module = metadata.module_path().unwrap_or(target);
        let file = metadata.file().unwrap_or("");
        let filename = std::path::Path::new(file)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("");
        let lineno = metadata.line().unwrap_or(0);

        // ── Level (Python-compatible numeric mapping) ────────────
        let levelname = metadata.level().as_str();
        let levelno = level_to_python_number(metadata.level());

        // ── Process ─────────────────────────────────────────────
        let pid = std::process::id();

        // ── Relative timestamps ─────────────────────────────────
        let relative_created = self.start_time.elapsed().as_secs_f64() * 1000.0;
        let created = ts.timestamp() as f64 + ts.timestamp_subsec_millis() as f64 / 1000.0;
        let msecs = ts.timestamp_subsec_millis() as f64;
        let asctime = ts.format("%Y-%m-%dT%H:%M:%S%.3f").to_string();

        // ── Full formatted line (skellylog style) ────────────────
        let level_padded = format!("{levelname:<5}");
        let formatted_message = format!(
            ">> {} |  {} |  {} |  {}:{} |  {} |  PID:{}:{} |  TID:{}:{}\n",
            plain_message,
            level_padded,
            delta_ms,
            target,
            lineno,
            asctime,
            pid,
            self.process_name,
            tid,
            tname,
        );

        // ── Build JSON ──────────────────────────────────────────
        let payload = serde_json::json!({
            "name": target,
            "msg": plain_message,
            "args": [],
            "levelname": levelname,
            "levelno": levelno,
            "pathname": file,
            "filename": filename,
            "module": module,
            "lineno": lineno,
            "funcName": "",
            "created": created,
            "msecs": msecs,
            "relativeCreated": relative_created,
            "thread": tid.parse::<i64>().unwrap_or(0),
            "threadName": tname,
            "processName": self.process_name,
            "process": pid,
            "delta_t": delta_ms,
            "message": plain_message,
            "asctime": asctime,
            "formatted_message": formatted_message,
            "type": "LogRecord",
            "message_type": "log_record",
            "exc_info": null,
            "exc_text": null,
            "stack_info": null,
        });

        let _ = sender.send(payload.to_string());
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Map `tracing::Level` to Python `logging` level numbers so the frontend
/// level-name filtering (`LOG_COLORS` map) matches exactly.
///
/// Python mapping:
///   CRITICAL = 50, ERROR = 40, WARNING = 30, INFO = 20, DEBUG = 10, TRACE = 5
const fn level_to_python_number(level: &tracing::Level) -> i32 {
    match *level {
        tracing::Level::TRACE => 5,
        tracing::Level::DEBUG => 10,
        tracing::Level::INFO => 20,
        tracing::Level::WARN => 30,
        tracing::Level::ERROR => 40,
    }
}