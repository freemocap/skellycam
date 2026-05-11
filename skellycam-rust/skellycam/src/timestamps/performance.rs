use std::sync::OnceLock;
use std::time::Instant;

static PROCESS_START: OnceLock<Instant> = OnceLock::new();

pub fn performance_counter_nanoseconds() -> i64 {
    let start = PROCESS_START.get_or_init(Instant::now);
    start.elapsed().as_nanos() as i64
}
