# Check system information
#systeminfo || Write-Host "Unable to fetch system information"

# Ensure Python 3.11 is installed and added to your PATH
#Write-Host "Ensure Python 3.11 is installed and added to your PATH."

# Print the Python executable path
python -c "import sys; print(sys.executable)"

# Upgrade pip and install dependencies without using cache
python -m pip install --upgrade pip --no-cache-dir
pip install -e . --no-cache-dir

# Freeze dependencies to requirements.txt
pip freeze > requirements.txt

# Remove opencv-python dependency from requirements.txt
(Get-Content requirements.txt) -notmatch 'opencv-python' | Set-Content requirements.txt

# Set environment variables for PyApp
$env:PYAPP_PROJECT_NAME = "skellycam-server"
$env:PYAPP_PROJECT_VERSION = "v2.0.1"
$env:PYAPP_PYTHON_VERSION = "3.11"
$env:PYAPP_PROJECT_DEPENDENCY_FILE = (Resolve-Path "requirements.txt").Path
$env:PYAPP_EXEC_SCRIPT = (Resolve-Path "skellycam\run_skellycam_server.py").Path
$env:PYAPP_PIP_EXTRA_ARGS = "--no-deps --no-cache-dir"
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

# Return to the initial directory
Set-Location ..

# Construct the path to the executable in the bin folder
$binPath = Join-Path -Path $extractedDir -ChildPath "bin\pyapp.exe"

# Copy the executable to the current working directory
Copy-Item -Path $binPath -Destination (Get-Location)

# Rename the executable in the current working directory
Rename-Item -Path ".\pyapp.exe" -NewName "skellycam-server.exe"

# Ensure Chocolatey is installed on your system
# Install Rcedit with Chocolatey (uncomment to install Rcedit, which should be used to set the executable icon)
# You should only run this choco command from an elevated PowerShell session
#choco install rcedit -y

# Set executable icon
# Uncomment and specify the correct path for your icon if needed
rcedit "skellycam-server.exe" --set-icon "shared/skellycam-logo/skellycam-favicon.ico"


# Clean up: Remove the downloaded and extracted files, except for the .exe
Remove-Item -Recurse -Force "pyapp.zip"
Remove-Item -Recurse -Force $extractedDir
Remove-Item -Force "requirements.txt"