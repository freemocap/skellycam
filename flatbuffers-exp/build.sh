#!/bin/bash

echo "🔨 Building FlatBuffers schemas for Tauri architecture..."

# Install flatc if not present
if ! command -v flatc &> /dev/null; then
    echo "Installing flatc..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install flatbuffers
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update
        sudo apt-get install -y flatbuffers-compiler
    else
        echo "Please install flatbuffers manually"
        exit 1
    fi
fi

# Create output directories
mkdir -p server/generated/
mkdir -p flatbuffers-tauri/src-tauri/src/generated/
mkdir -p flatbuffers-tauri/src/generated/

# Generate Python code
echo "Generating Python code..."
flatc --python -o server/generated/ schemas/message.fbs

# Generate Rust code
echo "Generating Rust code..."
flatc --rust -o flatbuffers-tauri/src-tauri/src/generated/ schemas/message.fbs

# Generate TypeScript code (for types only)
echo "Generating TypeScript code..."
flatc --ts -o flatbuffers-tauri/src/generated/ schemas/message.fbs

echo "✅ FlatBuffers build complete!"
echo ""
echo "Next steps:"
echo "1. pip install -r server/requirements.txt"
echo "2. cargo build (in src-tauri/)"
echo "3. npm install"
echo "4. python server/server.py"
echo "5. npm run tauri dev"