#!/bin/bash

echo "🔨 Building FlatBuffers schemas..."

# Install flatc if not present
if ! command -v flatc &> /dev/null; then
    echo "Installing flatc..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install flatbuffers
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update
        sudo apt-get install -y flatbuffers-compiler
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "Please install flatbuffers manually for Windows"
        echo "Download from: https://github.com/google/flatbuffers/releases"
        echo "Add flatc.exe to your PATH"
        exit 1
    fi
fi

# Create output directories if they don't exist
mkdir -p server/
mkdir -p src/renderer/src/generated/

# Generate Python code
echo "Generating Python code..."
flatc --python -o server/ schemas/message.fbs

# Generate TypeScript code
echo "Generating TypeScript code..."
flatc --ts -o flatbuffer-demo/src/renderer/src/generated/ schemas/message.fbs

echo "✅ FlatBuffers build complete!"
echo ""
echo "Next steps:"
echo "1. Install Python dependencies: pip install -r server/requirements.txt"
echo "2. Install npm dependencies: npm install"
echo "3. Start Python server: python server/server.py"
echo "4. Start Electron app: npm run dev"
