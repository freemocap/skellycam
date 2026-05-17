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

impl std::fmt::Debug for BreakableBarrier {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("BreakableBarrier").finish_non_exhaustive()
    }
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

    /// Change the expected participant count. Intended to be called when
    /// the camera group's camera set changes (add or remove cameras).
    ///
    /// SAFETY: Only call this when no participants are blocked at `wait()` —
    /// otherwise the new total may not match the partial count and the
    /// barrier may release at the wrong moment. The intended call site is
    /// inside `CameraGroup::apply()` while the group is paused (cameras
    /// are in their responsive polling loops, not at the barrier).
    ///
    /// If `count` is non-zero (some participants have already called
    /// `wait()`), this resets `count` to zero to avoid the new total
    /// being satisfied prematurely. Bumps `generation` so any thread
    /// that does happen to be waiting wakes up and re-checks.
    pub fn set_total(&self, new_total: usize) {
        assert!(new_total > 0, "BreakableBarrier requires at least 1 participant");
        let (lock, cvar) = &*self.inner;
        let mut state = lock.lock().unwrap();
        state.total = new_total;
        state.count = 0;
        state.generation += 1;
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
