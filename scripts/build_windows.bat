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

:: Get SkellyCam version
echo Getting SkellyCam version...
setlocal
set "PYTHONPATH=..\skellycam"
for /f "delims=" %%i in ('python -c "import skellycam; print(skellycam.__version__)"') do set "VERSION=%%i"
endlocal & set "VERSION=%VERSION%"

:: Get Path to skellycam.__main__.py
echo Getting path to skellycam.__main__.py...
setlocal
set "PYTHONPATH=..\skellycam"
for /f "delims=" %%i in ('python -c "import os; import skellycam.__main__; print(os.path.abspath(skellycam.__main__.__file__))"') do set "SKELLYCAM_MAIN_PATH=%%i"
endlocal & set "SKELLYCAM_MAIN_PATH=%SKELLYCAM_MAIN_PATH%"
echo Using SkellyCam version %VERSION% at %SKELLYCAM_MAIN_PATH% as the executable script.


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

:: Export a requirements.txt file
echo Exporting requirements file to: %cd%\requirements.txt
uv pip freeze > "%cd%\requirements.txt"

:: Set environment variables for PyApp
set PYAPP_PROJECT_NAME=skellycam
set PYAPP_PROJECT_VERSION=%VERSION%
set PYAPP_PROJECT_DEPENDENCY_FILE="%cd%\requirements.txt"
set PYAPP_PYTHON_VERSION=3.11
set PYAPP_UV_ENABLED = true
set PYAPP_EXEC_SCRIPT=%SKELLYCAM_PATH%
set PYAPP_EXPOSE_ALL_COMMANDS=true
set RUST_BACKTRACE=full

:: Build the project
echo Building the project...
cargo build --release

:: Install PyApp
cargo install pyapp --force --root ..

:: Rename the executable
cd ..
move bin\pyapp.exe bin\skellycam_windows_exe_x86_64-pc-windows-msvc.exe

:: Check if rcedit is installed
where rcedit >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing Rcedit with Chocolatey...
    choco install rcedit -y
)

:: Set the executable icon
echo Setting the executable icon...
rcedit "skellycam_windows_exe_x86_64-pc-windows-msvc.exe" --set-icon "shared\skellycam-logo\skellycam-favicon.ico"

echo Build completed successfully. Executable is %cd%\bin\skellycam_windows_exe_x86_64-pc-windows-msvc.exe