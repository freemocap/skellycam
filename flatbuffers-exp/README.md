# FlatBuffer IPC Demo - Complete Setup Guide

A cross-platform demo showing zero-copy inter-process communication between Python and Electron using FlatBuffers and shared memory-mapped files.

## 🎯 Architecture

- **Server (Python)**: FastAPI server that writes camera frame data to memory-mapped files using FlatBuffers
- **Client (Electron + React + TypeScript)**: Desktop app that reads shared memory and displays live data
- **Protocol**: FlatBuffers for serialization, memory-mapped files for IPC, WebSocket for notifications

## 📋 Prerequisites

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **FlatBuffers compiler** (`flatc`)

## 🚀 Step-by-Step Setup

### 1. Project Structure Setup

```bash
# Create main project directory
mkdir flatbuffer-ipc-demo
cd flatbuffer-ipc-demo

# Create directory structure
mkdir -p server schemas
```

### 2. Install FlatBuffers Compiler

**macOS:**
```bash
brew install flatbuffers
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y flatbuffers-compiler
```

**Windows:**
1. Download from: https://github.com/google/flatbuffers/releases
2. Extract `flatc.exe`
3. Add to PATH

Verify installation:
```bash
flatc --version
```

### 3. Create FlatBuffers Schema

Save the `message.fbs` file to `schemas/message.fbs`

### 4. Python Server Setup

```bash
cd server

# Create requirements.txt
cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn[standard]==0.24.0
flatbuffers==24.3.25
numpy==1.26.2
websockets==12.0
EOF

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Save the updated `server.py` to `server/server.py`

### 5. Generate FlatBuffers Code

```bash
# From project root
chmod +x build.sh
./build.sh
```

This generates:
- `server/SharedData/*.py` - Python FlatBuffers code
- `flatbuffer-client/src/generated/*.ts` - TypeScript FlatBuffers code

### 6. Electron Client Setup

```bash
# Create Electron app
npm create @quick-start/electron@latest flatbuffer-client

# Choose options:
# - Template: react-ts
# - Package manager: npm

cd flatbuffer-client

# Install dependencies
npm install
npm install flatbuffers zod
npm install --save-dev @types/node
```

### 7. Configure Client Files

Replace or create the following files in `flatbuffer-client/`:

- `package.json` - Use the provided configuration
- `vite.config.ts` - Vite configuration with Electron plugin
- `tsconfig.json` - TypeScript configuration
- `tsconfig.electron.json` - Electron-specific TypeScript config
- `electron/main.ts` - Main Electron process
- `electron/preload.ts` - Preload script for IPC
- `src/types/window.d.ts` - Window type definitions
- `src/types/shared-memory.ts` - Shared memory types
- `src/schemas/validation.ts` - Zod validation schemas
- `src/hooks/useSharedMemory.ts` - React hook for shared memory
- `src/components/App.tsx` - Main React component
- `src/main.tsx` - React entry point
- `src/index.css` - Global styles
- `index.html` - HTML entry point

### 8. Re-generate FlatBuffers with Correct Paths

After setting up the client, regenerate the FlatBuffers code:

```bash
# From project root
flatc --python -o server/ schemas/message.fbs
flatc --ts -o flatbuffer-client/src/generated/ schemas/message.fbs
```

## 🎮 Running the Demo

### Terminal 1: Start Python Server

```bash
cd server
source venv/bin/activate  # On Windows: venv\Scripts\activate
python server.py
```

You should see:
```
🚀 Starting FlatBuffer IPC Demo Server
📁 Memory-mapped file: /tmp/fbuffer_camera_data.mmap
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Start Electron Client

```bash
cd flatbuffer-client
npm run dev
```

The Electron app should launch and automatically connect to the Python server!

## 🔧 Development Workflow

### Python Server Development

```bash
cd server
source venv/bin/activate
python server.py
```

The server runs on `http://localhost:8000`

### Client Development

```bash
cd flatbuffer-client
npm run dev
```

Hot reload is enabled for both React and Electron.

### Rebuild FlatBuffers

If you modify `schemas/message.fbs`:

```bash
./build.sh
```

## 📦 Building for Production

```bash
cd flatbuffer-client
npm run build
```

This creates a distributable Electron app in `flatbuffer-client/release/`

## 🐛 Troubleshooting

### "flatc: command not found"
Install FlatBuffers compiler (see Prerequisites section)

### "Module not found: SharedData"
Run `./build.sh` to generate FlatBuffers code

### WebSocket connection failed
1. Ensure Python server is running on port 8000
2. Check firewall settings

### Memory-mapped file not found
1. Verify Python server started successfully
2. Check `/tmp` directory (Linux/Mac) or `%TEMP%` (Windows)
3. Ensure file permissions allow reading

### TypeScript errors in generated code
Regenerate FlatBuffers code with latest flatc version

## 🌟 Key Features

✅ **Cross-Platform**: Works on Windows, macOS, and Linux  
✅ **Zero-Copy**: Direct memory access without serialization overhead  
✅ **Type-Safe**: Full TypeScript with Zod validation  
✅ **Real-Time**: 30 FPS updates via WebSocket notifications  
✅ **Modern Stack**: Vite + React + Electron + FastAPI

## 📝 Project Structure

```
flatbuffer-ipc-demo/
├── schemas/
│   └── message.fbs           # FlatBuffers schema
├── server/
│   ├── server.py             # Python FastAPI server
│   ├── requirements.txt      # Python dependencies
│   └── SharedData/           # Generated Python code
└── flatbuffer-client/
    ├── electron/
    │   ├── main.ts           # Electron main process
    │   └── preload.ts        # Preload script
    ├── src/
    │   ├── components/
    │   │   └── App.tsx       # Main React component
    │   ├── generated/        # Generated TypeScript code
    │   ├── hooks/
    │   │   └── useSharedMemory.ts
    │   ├── schemas/
    │   │   └── validation.ts # Zod schemas
    │   ├── types/
    │   │   ├── window.d.ts
    │   │   └── shared-memory.ts
    │   ├── main.tsx
    │   └── index.css
    ├── package.json
    ├── vite.config.ts
    └── tsconfig.json
```

## 🔐 Security Notes

- The preload script uses `contextIsolation: true` for security
- Only specific IPC channels are exposed via `contextBridge`
- File reading is restricted to the memory-mapped file path

## 📚 Technologies Used

- **Python**: FastAPI, FlatBuffers, NumPy
- **TypeScript**: React, Electron, Vite
- **Validation**: Zod
- **IPC**: Memory-mapped files, WebSocket
- **Serialization**: FlatBuffers

