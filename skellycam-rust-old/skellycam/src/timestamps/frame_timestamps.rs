//! FrameTimestamps: stack-allocated timestamp struct for the hot path.
//! 6 × i64 = 48 bytes, zero heap allocation, trivially Copy.
//! Converts to extensible BTreeMap representation for storage/CSV output.

use std::collections::BTreeMap;
use crate::timestamps::stages::TimestampStage;

/// Per-frame timestamps collected across the pipeline.
/// Stack-allocated for zero overhead in the hot loop.
#[derive(Debug, Clone, Copy)]
pub struct FrameTimestamps {
    pub pre_frame_grab_nanoseconds: i64,
    pub post_frame_grab_nanoseconds: i64,
    pub pre_frame_decode_nanoseconds: i64,
    pub post_frame_decode_nanoseconds: i64,
    pub pre_frame_record_nanoseconds: i64,
    pub post_frame_record_nanoseconds: i64,
}

impl FrameTimestamps {
    /// Create with all fields zeroed.
    pub fn new() -> Self {
        Self {
            pre_frame_grab_nanoseconds: 0,
            post_frame_grab_nanoseconds: 0,
            pre_frame_decode_nanoseconds: 0,
            post_frame_decode_nanoseconds: 0,
            pre_frame_record_nanoseconds: 0,
            post_frame_record_nanoseconds: 0,
        }
    }

    /// Convert hot-path struct to extensible map for storage and analysis.
    pub fn to_stage_map(&self) -> BTreeMap<TimestampStage, i64> {
        let mut map = BTreeMap::new();
        map.insert(TimestampStage::PreFrameGrab, self.pre_frame_grab_nanoseconds);
        map.insert(TimestampStage::PostFrameGrab, self.post_frame_grab_nanoseconds);
        map.insert(TimestampStage::PreFrameDecode, self.pre_frame_decode_nanoseconds);
        map.insert(TimestampStage::PostFrameDecode, self.post_frame_decode_nanoseconds);
        map.insert(TimestampStage::PreFrameRecord, self.pre_frame_record_nanoseconds);
        map.insert(TimestampStage::PostFrameRecord, self.post_frame_record_nanoseconds);
        map
    }

    /// The grab midpoint is the best proxy for "when were these photons captured."
    pub fn grab_midpoint_nanoseconds(&self) -> i64 {
        (self.pre_frame_grab_nanoseconds + self.post_frame_grab_nanoseconds) / 2
    }
}
