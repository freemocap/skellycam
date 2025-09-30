Write-Host "Building FlatBuffers schemas for Tauri architecture..." -ForegroundColor Cyan

# Check if flatc is installed
if (-not (Get-Command flatc -ErrorAction SilentlyContinue)) {
    Write-Host "flatc not found. Installing via winget..." -ForegroundColor Yellow
    winget install Google.FlatBuffers

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install. Please install manually from:" -ForegroundColor Red
        Write-Host "https://github.com/google/flatbuffers/releases" -ForegroundColor Red
        exit 1
    }
}

# Create output directories
New-Item -ItemType Directory -Force -Path "server\generated\" | Out-Null
New-Item -ItemType Directory -Force -Path "flatbuffers-tauri\src-tauri\src\generated\" | Out-Null
New-Item -ItemType Directory -Force -Path "flatbuffers-tauri\src\generated\" | Out-Null

# Generate Python code
Write-Host "Generating Python code..." -ForegroundColor Green
flatc --python -o server\generated\ schemas\message.fbs

# Generate Rust code
Write-Host "Generating Rust code..." -ForegroundColor Green
flatc --rust -o flatbuffers-tauri\src-tauri\src\generated\ schemas\message.fbs

# Generate TypeScript code
Write-Host "Generating TypeScript code..." -ForegroundColor Green
flatc --ts -o flatbuffers-tauri\src\generated\ schemas\message.fbs

Write-Host ""
Write-Host "FlatBuffers build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. pip install -r server\requirements.txt"
Write-Host "2. cargo build (in src-tauri\)"
Write-Host "3. npm install"
Write-Host "4. python server\server.py"
Write-Host "5. npm run tauri dev"