@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d C:\Users\jonma\code_repos\github\jonmatthis\openpnp-capture\build
nmake
cd /d C:\Users\jonma\code_repos\github\freemocap\skellycam\skellycam-rust\tools\openpnp-capture-poc
echo === CLEANING RUST ===
cargo clean
echo.
echo === BUILDING RUST + RUNNING with args: %* ===
cargo run --release %*
