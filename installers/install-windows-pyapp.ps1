# Check system information
#systeminfo || Write-Host "Unable to fetch system information"

# Ensure Python 3.11 is installed and added to your PATH
#Write-Host "Ensure Python 3.11 is installed and added to your PATH."

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -e .

# Freeze dependencies to requirements.txt
pip freeze > pyapp-requirements.txt

# Remove opencv-python dependency from requirements.txt
(Get-Content pyapp-requirements.txt) -notmatch 'opencv-python' | Set-Content requirements.txt

# Set environment variables for PyApp
$env:PYAPP_PROJECT_NAME = "skellycam"
$env:PYAPP_PROJECT_VERSION = "v2.0.0"
$env:PYAPP_PYTHON_VERSION = "3.11"
$env:PYAPP_PROJECT_DEPENDENCY_FILE = (Resolve-Path "pyapp-requirements.txt").Path
$env:PYAPP_EXEC_SCRIPT = (Resolve-Path "skellycam\run_skellycam_server.py").Path
$env:PYAPP_PIP_EXTRA_ARGS = "--no-deps"
$env:PYAPP_EXPOSE_ALL_COMMANDS = "true"


# Define the GitHub repository
$repo = "ofek/pyapp"

# Get the latest release information using the GitHub API
$latestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest"

# Extract the version number and URL for the asset you want
$version = $latestRelease.tag_name -replace 'v', ''
$asset = $latestRelease.assets | Where-Object { $_.name -eq "source.zip" }

# Download the asset
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile "pyapp.zip"

# Unzip PyApp
Expand-Archive -Path "pyapp.zip" -DestinationPath "."

# Determine the extracted folder name based on the version
$extractedDir = "pyapp-v$version"

# Navigate to the directory containing Cargo.toml
Set-Location $extractedDir

# Build and install PyApp (requires Rust and Cargo)
# Install Rust from https://rustup.rs/ if not installed
cargo build --release
cargo install pyapp --force --root (Get-Location).Path

## Return to the initial directory
Set-Location ..

# Construct the path to the executable in the bin folder
$binPath = Join-Path -Path $extractedDir -ChildPath "bin\pyapp.exe"

# Rename the executable
Rename-Item -Path $binPath -NewName "skellycam_app.exe"

# Install Rcedit with Chocolatey
# Ensure Chocolatey is installed on your system
choco install rcedit -y

# Set executable icon
# Uncomment and specify the correct path for your icon if needed
rcedit "skellycam_app.exe" --set-icon "freemocap/shared/skellycam-logo/skellycam-favicon.ico"

Write-Host "skellycam_app.exe has been created with the specified icon."