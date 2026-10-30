//! Lightweight server launcher for integration tests.
//!
//! Starts the full Axum router on an OS-assigned port, runs it in a
//! background tokio task, and returns the bound address + a shutdown
//! trigger so the test can stop the server cleanly.

use std::net::SocketAddr;
use std::sync::atomic::Ordering;
use std::sync::Arc;

use tokio::net::TcpListener;
use tokio::sync::oneshot;

use super::AppState;

/// Handle for a running test server. Drop (or call `shutdown()`) to stop it.
pub struct TestServer {
    pub addr: SocketAddr,
    shutdown_tx: Option<oneshot::Sender<()>>,
    state: Arc<AppState>,
}

impl TestServer {
    /// Signal the server to shut down and wait for the task to finish.
    pub async fn shutdown(mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            self.state.shutdown_flag.store(true, Ordering::SeqCst);
            let _ = tx.send(());
        }
        // Give the server a moment to drain
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
    }
}

impl Drop for TestServer {
    fn drop(&mut self) {
        // Best-effort shutdown on drop
    }
}

/// Start the full Axum router on `127.0.0.1:0`, returning the bound
/// address and a handle that shuts the server down when dropped (or
/// when `shutdown()` is called explicitly).
pub async fn start_test_server() -> anyhow::Result<TestServer> {
    let state = Arc::new(AppState::new());
    let router = super::build_router(state.clone());

    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;

    let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();
    let shutdown_flag = state.shutdown_flag.clone();

    tokio::spawn(async move {
        axum::serve(listener, router)
            .with_graceful_shutdown(async move {
                let _ = shutdown_rx.await;
                // Also poll the flag in case /shutdown endpoint was called
                loop {
                    if shutdown_flag.load(Ordering::SeqCst) {
                        break;
                    }
                    tokio::time::sleep(std::time::Duration::from_millis(50)).await;
                }
            })
            .await
            .ok();
    });

    // Let the server bind
    tokio::time::sleep(std::time::Duration::from_millis(50)).await;

    Ok(TestServer {
        addr,
        shutdown_tx: Some(shutdown_tx),
        state,
    })
}
