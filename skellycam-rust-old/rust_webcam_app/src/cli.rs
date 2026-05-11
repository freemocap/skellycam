//! CLI argument parsing via `clap` derive.
//!
//! ## Python analogy
//!
//! `clap` is Rust's equivalent of Python's `argparse`.  The `#[derive(Parser)]`
//! attribute is a **derive macro** — it generates code at compile time by
//! inspecting the struct fields.  This is similar to Python's dataclass
//! decorator, but far more powerful: derive macros can generate trait
//! implementations, validation logic, and in this case, an entire CLI parser.
//!
//! Each `#[arg(...)]` attribute configures the generated parser for that field,
//! much like `parser.add_argument(...)` in argparse.
//!
//! ## Key Rust concept: attributes
//!
//! `#[...]` syntax denotes an **attribute** in Rust.  Attributes attach metadata
//! to items (structs, functions, fields, etc.) and are processed at compile
//! time.  Some are built into the language (`#[derive(...)]`), others come from
//! libraries (`#[arg(...)]`).  Crates opt in to this with `#[macro_use]` or by
//! importing specific macros.

use clap::Parser;

// ── CLI ───────────────────────────────────────────────────────────────

/// Command-line arguments for the webcam application.
///
/// `#[derive(Parser)]` tells `clap` to generate a parser from this struct.
/// Each field becomes a command-line flag/option.  The doc comments (`///`)
/// on each field become the `--help` text — this is an enforced Rust convention.
#[derive(Parser)]
#[command(name = "webcam_app")]
#[command(about = "USB Webcam — live preview, controls, and MP4 recording")]
pub(crate) struct Arguments {
    /// Camera index to open (use --list to see available cameras)
    #[arg(short, long, default_value = "0")]
    pub camera: u32,

    /// List all connected cameras and exit
    #[arg(short, long)]
    pub list: bool,

    /// Output video file path (MP4)
    #[arg(short, long, default_value = "output.mp4")]
    pub output: String,

    /// Desired capture width (0 = camera decides)
    #[arg(long, default_value = "0")]
    pub width: u32,

    /// Desired capture height (0 = camera decides)
    #[arg(long, default_value = "0")]
    pub height: u32,

    /// Frame rate for recording
    #[arg(long, default_value = "30")]
    pub frames_per_second: u32,

    /// Maximum display dimension in pixels (scales down if exceeded; 0 = no limit)
    #[arg(long, default_value = "1200")]
    pub maximum_dimension: u32,
}
