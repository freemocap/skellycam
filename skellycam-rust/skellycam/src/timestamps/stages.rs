//! TimestampStage enum: extensible pipeline stage definitions.
//! New stages can be added without changing duration computation or CSV output.

/// A named stage in the frame processing pipeline, in execution order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum TimestampStage {
    PreFrameGrab,
    PostFrameGrab,
    PreFrameDecode,
    PostFrameDecode,
    PreFrameRecord,
    PostFrameRecord,
}

impl TimestampStage {
    /// Human-readable name for CSV columns and statistics display.
    pub fn display_name(self) -> &'static str {
        match self {
            Self::PreFrameGrab => "pre_frame_grab",
            Self::PostFrameGrab => "post_frame_grab",
            Self::PreFrameDecode => "pre_frame_decode",
            Self::PostFrameDecode => "post_frame_decode",
            Self::PreFrameRecord => "pre_frame_record",
            Self::PostFrameRecord => "post_frame_record",
        }
    }

    /// Whether this is a "pre" marker (start of an operation).
    pub fn is_pre(self) -> bool {
        matches!(
            self,
            Self::PreFrameGrab | Self::PreFrameDecode | Self::PreFrameRecord
        )
    }

    /// The matching post stage for a pre stage, and vice versa.
    pub fn pair(self) -> TimestampStage {
        match self {
            Self::PreFrameGrab => Self::PostFrameGrab,
            Self::PostFrameGrab => Self::PreFrameGrab,
            Self::PreFrameDecode => Self::PostFrameDecode,
            Self::PostFrameDecode => Self::PreFrameDecode,
            Self::PreFrameRecord => Self::PostFrameRecord,
            Self::PostFrameRecord => Self::PreFrameRecord,
        }
    }
}
