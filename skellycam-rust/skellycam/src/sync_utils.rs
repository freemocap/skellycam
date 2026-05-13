//! Synchronization primitives for the camera pipeline.
//!
//! `BreakableBarrier` is a std::sync::Barrier replacement that supports
//! being "broken" on shutdown — all waiting threads are released immediately
//! instead of blocking forever because the expected thread count can never be met.

use std::sync::{Arc, Condvar, Mutex};

struct Inner {
    count: usize,
    total: usize,
    generation: u64,
    broken: bool,
}

pub struct BreakableBarrier {
    inner: Arc<(Mutex<Inner>, Condvar)>,
}

impl BreakableBarrier {
    pub fn new(total: usize) -> Self {
        assert!(total > 0, "BreakableBarrier requires at least 1 participant");
        Self {
            inner: Arc::new((
                Mutex::new(Inner {
                    count: 0,
                    total,
                    generation: 0,
                    broken: false,
                }),
                Condvar::new(),
            )),
        }
    }

    /// Returns `true` if the barrier released normally (all threads arrived).
    /// Returns `false` if the barrier was broken (shutdown in progress).
    pub fn wait(&self) -> bool {
        let (lock, cvar) = &*self.inner;
        let mut state = lock.lock().unwrap();

        if state.broken {
            return false;
        }

        state.count += 1;
        let my_gen = state.generation;

        if state.count == state.total {
            // All threads arrived — release them all
            state.count = 0;
            state.generation += 1;
            cvar.notify_all();
            return true;
        }

        // Wait for other threads — but wake up if barrier is broken
        while state.count < state.total && state.generation == my_gen && !state.broken {
            state = cvar.wait(state).unwrap();
        }

        if state.broken {
            return false;
        }
        true
    }

    /// Break the barrier. All currently waiting threads are released
    /// with `wait()` returning `false`. Subsequent `wait()` calls also
    /// return `false` immediately.
    pub fn break_barrier(&self) {
        let (lock, cvar) = &*self.inner;
        let mut state = lock.lock().unwrap();
        state.broken = true;
        cvar.notify_all();
    }
}

impl Clone for BreakableBarrier {
    fn clone(&self) -> Self {
        Self {
            inner: self.inner.clone(),
        }
    }
}
