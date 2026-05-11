//! # webcam_app — USB webcam preview, controls, and recording
//!
//! This is the crate root.  It declares all modules and provides the `main()`
//! entry point.
//!
//! ## Python analogy
//!
//! In Python, `import` looks for `.py` files in `sys.path`.  In Rust, `mod`
//! declarations tell the compiler which source files belong to the crate.
//! There is no dynamic import — the module tree is fixed at compile time.
//!
//! A Rust module can be either:
//! - a single file: `src/foo.rs`  → `mod foo;`
//! - a directory with a `mod.rs`: `src/foo/mod.rs` → `mod foo;`
//!
//! The `pub(crate)` visibility you'll see throughout means "public within this
//! crate, but not visible to external crates that depend on us."  Think of it
//! like Python's convention of a leading underscore (`_internal`), but enforced
//! by the compiler instead of by social contract.

mod app;
mod camera;
mod cli;
mod controls;
mod display;
mod pipeline;
mod recorder;
mod timing;

use anyhow::Result;
use clap::Parser;
use cli::Arguments;

/// Entry point.  Parses CLI arguments and hands off to `app::run()`.
///
/// `main()` returns `Result<()>` via anyhow, so `?` can be used throughout.
/// If an error propagates all the way out, anyhow prints a formatted message
/// (including the error chain / "context" stack) and exits with code 1.
///
/// Python analogy: this is like wrapping your script in
/// ```python
/// try:
///     main()
/// except Exception as e:
///     print(e, file=sys.stderr)
///     sys.exit(1)
/// ```
fn main() -> Result<()> {
    let arguments = Arguments::parse();
    app::run(arguments)
}
