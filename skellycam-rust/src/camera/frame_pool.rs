//! Frame buffers the camera driver writes into once, reused when every consumer has dropped them.
//!
//! Each camera thread owns a pool. A frame's bytes travel downstream (gatherer, dispatcher, recorder, previews,
//! tracker pixels) as `Arc` clones of one pooled buffer; when the last clone drops, the buffer is free again. The
//! pool grows only while more frames are in flight than ever before (start-up, a slow recorder: frames are never
//! dropped), so steady-state capture allocates nothing.

use std::sync::Arc;

/// One frame's bytes: written once by the driver, shared by reference count.
pub type FrameBytes = Arc<Vec<u8>>;

#[derive(Default)]
pub struct FramePool {
    buffers: Vec<FrameBytes>,
}

impl FramePool {
    /// A buffer no consumer holds, emptied, with room for at least `capacity` bytes. Write it through
    /// `Arc::get_mut`, then share it with `Arc::clone`.
    pub fn take(&mut self, capacity: usize) -> &mut FrameBytes {
        let free = self.buffers.iter().position(|buffer| Arc::strong_count(buffer) == 1 && Arc::weak_count(buffer) == 0);
        let index = free.unwrap_or_else(|| {
            self.buffers.push(Arc::new(Vec::with_capacity(capacity)));
            self.buffers.len() - 1
        });
        let buffer = Arc::get_mut(&mut self.buffers[index]).expect("a free pooled buffer has no other owner");
        buffer.clear();
        buffer.reserve(capacity);
        &mut self.buffers[index]
    }

    /// Buffers allocated so far (free and in flight).
    pub fn allocated(&self) -> usize {
        self.buffers.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fill(pool: &mut FramePool, bytes: &[u8]) -> FrameBytes {
        let slot = pool.take(bytes.len());
        Arc::get_mut(slot).unwrap().extend_from_slice(bytes);
        Arc::clone(slot)
    }

    #[test]
    fn released_buffers_are_reused_without_allocating() {
        let mut pool = FramePool::default();
        for round in 0..100u8 {
            let frame = fill(&mut pool, &[round; 1000]);
            assert_eq!(frame.as_slice(), &[round; 1000][..]);
            drop(frame);
        }
        assert_eq!(pool.allocated(), 1);
    }

    #[test]
    fn a_held_frame_is_never_overwritten() {
        let mut pool = FramePool::default();
        let held = fill(&mut pool, b"first");
        let second = fill(&mut pool, b"second");
        assert_eq!((held.as_slice(), second.as_slice()), (&b"first"[..], &b"second"[..]));
        assert_eq!(pool.allocated(), 2);
        drop(second);
        let third = fill(&mut pool, b"third");
        assert_eq!((held.as_slice(), third.as_slice(), pool.allocated()), (&b"first"[..], &b"third"[..], 2));
    }

    #[test]
    fn capacity_grows_only_for_a_bigger_frame() {
        let mut pool = FramePool::default();
        drop(fill(&mut pool, &[1; 64]));
        let capacity = pool.take(16).capacity();
        assert!(capacity >= 64);
        assert!(pool.take(4096).capacity() >= 4096);
        assert_eq!(pool.allocated(), 1);
    }
}
