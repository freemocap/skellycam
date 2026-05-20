//! CLI argument types — parsed by clap derive.
//!
//! These structs ARE the config passed to each test module.
//! No separate config types, no stringly-typed args.

use clap::{Parser, Subcommand};

/// SkellyCam Rust — multi-camera recording and test harness.
#[derive(Parser)]
#[command(name = "skellycam-rust", version)]
pub struct Cli {
    /// Start the web server on 0.0.0.0:53117
    #[arg(long, global = true)]
    pub serve: bool,

    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Start the HTTP + WebSocket server
    Serve,
    /// Run camera test modules
    Test {
        #[command(subcommand)]
        module: TestModule,
    },
}

#[derive(Subcommand)]
pub enum TestModule {
    /// Run the full test suite (1 camera through N cameras)
    All(AllArgs),
    /// Enumerate detected cameras
    Detect,
    /// Start → stream ~30 frames → shutdown
    Lifecycle(CameraCountArgs),
    /// Multi-camera lockstep streaming
    Multi(MultiArgs),
    /// CameraGroupManager lifecycle test
    Manager(CameraCountArgs),
    /// Full recording lifecycle test (warmup → record → verify disk)
    Recording(RecordingArgs),
    /// Pause / unpause / toggle test
    Pause(CameraCountArgs),
    /// Lossless JPEG rotation test (0/90/180/270 + record)
    Rotate(RotateArgs),
    /// Config update tests
    Update {
        #[command(subcommand)]
        module: UpdateModule,
    },
}

#[derive(Subcommand)]
pub enum UpdateModule {
    /// Scan exposure range and verify brightness response
    Exposure(CameraCountArgs),
    /// Toggle auto-exposure mode
    AutoExposure(CameraCountArgs),
    /// Sample resolution changes across supported formats
    Resolution(ResolutionArgs),
    /// Sample framerate changes across supported formats
    Framerate(FramerateArgs),
    /// Add a camera mid-stream
    AddCamera(CameraCountArgs),
    /// Remove a camera mid-stream
    RemoveCamera(CameraCountArgs),
}

// ── Argument structs ──────────────────────────────────────────────────────────

#[derive(clap::Args, Clone)]
pub struct AllArgs {
    /// Maximum number of cameras to test (default: all detected)
    #[arg(long = "max-cameras", value_name = "N")]
    pub max_cameras: Option<usize>,
}

#[derive(clap::Args, Clone)]
pub struct CameraCountArgs {
    /// Number of cameras to use (default: all detected)
    #[arg(long, value_name = "N")]
    pub cameras: Option<usize>,
}

#[derive(clap::Args, Clone)]
pub struct MultiArgs {
    /// Number of cameras to use
    #[arg(long)]
    pub cameras: Option<usize>,
    /// Specific camera indices (comma-separated, e.g. --indices 0,2,4)
    #[arg(long, value_delimiter = ',')]
    pub indices: Option<Vec<u32>>,
    /// Number of multiframes to capture
    #[arg(long = "max-loops", default_value = "60")]
    pub max_loops: i64,
}

#[derive(clap::Args, Clone)]
pub struct RecordingArgs {
    /// Number of cameras to use
    #[arg(long)]
    pub cameras: Option<usize>,
    /// Output directory for recordings
    #[arg(long, value_name = "PATH")]
    pub output: Option<String>,
}

/// Same fields as RecordingArgs — rotation test has its own CLI name.
pub type RotateArgs = RecordingArgs;

#[derive(clap::Args, Clone)]
pub struct ResolutionArgs {
    /// Camera index to reconfigure (default: 0)
    #[arg(long = "camera-index", default_value = "0")]
    pub camera_index: u32,
    /// Number of format samples to test (default: 5; 0 = all)
    #[arg(long, default_value = "5")]
    pub sample: usize,
}

/// Same fields as ResolutionArgs — framerate test has its own CLI name.
pub type FramerateArgs = ResolutionArgs;
