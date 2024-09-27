@echo off
setlocal enabledelayedexpansion

:: Check if Rust is installed
cargo --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Rust is not installed. Please install Rust from https://www.rust-lang.org/tools/install
    exit /b 1
)

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed. Please install Python 3.11 or later.
    exit /b 1
)

:: Check if PowerShell is available
powershell -command "exit" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo PowerShell is not available. Please run this script in a PowerShell environment.
    exit /b 1
)

:: Check if virtual environment exists
if exist .venv (
    echo Activating existing virtual environment...
    call .\.venv\Scripts\activate
    echo Updating dependencies...
    uv sync
) else (
    echo Creating new virtual environment...
    uv venv
    call .\.venv\Scripts\activate
    echo Installing dependencies...
    uv sync
)

:: Download PyApp
echo Downloading PyApp...
powershell -command "Invoke-WebRequest https://github.com/ofek/pyapp/releases/latest/download/source.zip -OutFile pyapp-source.zip"

:: Unzip PyApp using PowerShell
echo Unzipping PyApp...
powershell -command "Expand-Archive -Path pyapp-source.zip -DestinationPath ."

:: Rename the extracted directory
for /d %%i in (pyapp-v*) do set pyapp_dir=%%i
move %pyapp_dir% pyapp-latest
cd pyapp-latest

:: Get SkellyCam version
echo Getting SkellyCam version...
setlocal
set "PYTHONPATH=..\skellycam"
for /f "delims=" %%i in ('python -c "import skellycam; print(skellycam.__version__)"') do set "VERSION=%%i"
endlocal & set "VERSION=%VERSION%"

:: Set environment variables for PyApp
set PYAPP_PROJECT_NAME=skellycam
set PYAPP_PROJECT_VERSION=%VERSION%
set PYAPP_PYTHON_VERSION=3.11
set PYAPP_PROJECT_DEPENDENCY_FILE=..\requirements.txt
set PYAPP_EXEC_SCRIPT=..\skellycam\__main__.py
set PYAPP_PIP_EXTRA_ARGS=--no-deps
set PYAPP_EXPOSE_ALL_COMMANDS=true

:: Build the project
echo Building the project...
cargo build --release

:: Install PyApp
cargo install pyapp --force --root ..

:: Rename the executable
cd ..
move bin\pyapp.exe skellycam_windows_exe_x86_64-pc-windows-msvc.exe

:: Check if rcedit is installed
where rcedit >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing Rcedit with Chocolatey...
    choco install rcedit -y
)

:: Set the executable icon
echo Setting the executable icon...
rcedit "skellycam_windows_exe_x86_64-pc-windows-msvc.exe" --set-icon "skellycam\assets\logo\skellycam_skelly_logo.ico"

echo Build completed successfully. Executable is skellycam_windows_exe_x86_64-pc-windows-msvc.exe