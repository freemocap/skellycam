//! FrameDurations: computed from timestamp pairs.
//! Generic over stages — adding a new TimestampStage variant
//! automatically produces corresponding duration columns.

use std::collections::BTreeMap;
use crate::timestamps::stages::TimestampStage;

/// Computed durations for a single frame's journey through the pipeline.
#[derive(Debug, Clone)]
pub struct FrameDurations {
    /// Per-stage durations (e.g., "during_frame_grab_nanoseconds").
    pub stage_durations: BTreeMap<String, i64>,
    /// Idle/gap durations before each stage (e.g., "gap_before_frame_decode_nanoseconds").
    pub gap_durations: BTreeMap<String, i64>,
    /// End-to-end: post_record - pre_grab.
    pub total_processing_nanoseconds: i64,
}

impl FrameDurations {
    /// Compute all durations from an ordered set of timestamp stages.
    pub fn compute(timestamps: &BTreeMap<TimestampStage, i64>) -> Self {
        let entries: Vec<(TimestampStage, i64)> = timestamps
            .iter()
            .map(|(&stage, &nanoseconds)| (stage, nanoseconds))
            .collect();

        let mut stage_durations = BTreeMap::new();
        let mut gap_durations = BTreeMap::new();

        for window in entries.windows(2) {
            let ((stage_a, nanoseconds_a), (stage_b, nanoseconds_b)) = (window[0], window[1]);
            let difference = nanoseconds_b - nanoseconds_a;

            if stage_a.is_pre() && stage_b == stage_a.pair() {
                let base_name = stage_a
                    .display_name()
                    .strip_prefix("pre_")
                    .unwrap_or(stage_a.display_name());
                stage_durations.insert(
                    format!("during_{}_nanoseconds", base_name),
                    difference,
                );
            } else {
                gap_durations.insert(
                    format!("gap_before_{}_nanoseconds", stage_b.display_name()),
                    difference,
                );
            }
        }

        let total = timestamps
            .get(&TimestampStage::PostFrameRecord)
            .and_then(|&post| {
                timestamps
                    .get(&TimestampStage::PreFrameGrab)
                    .map(|&pre| post - pre)
            })
            .unwrap_or(0);

        Self {
            stage_durations,
            gap_durations,
            total_processing_nanoseconds: total,
        }
    }
}
