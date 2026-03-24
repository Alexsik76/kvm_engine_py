# IP-KVM Orchestrator (Python-based)

A unified orchestrator for Raspberry Pi 4 IP-KVM, managing hardware-accelerated video streaming and HID emulation.

## Architecture Overview

The system follows an **Event-Driven Orchestrator** pattern, where Python acts as the "brain" managing high-performance components:

- **Hardware Layer (`app/hardware/`)**: Native Python implementation for Linux ConfigFS (USB Gadget) and V4L2 (Video Bridge) initialization. Replaces legacy Shell scripts.
- **Service Layer (`app/services/`)**: 
    - `ProjectBuilder`: Automated C++ (GCC) and Go compiler orchestration.
    - `ServiceManager`: Asyncio-based lifecycle management for background processes.
- **Execution Layer (`src/`)**:
    - `video_engine` (C++): Hardware-accelerated H.264 encoding via V4L2.
    - `hid_server` (Go): Real-time HID emulation over WebSockets.
    - `MediaMTX`: High-efficiency WebRTC/RTSP streaming server.

## Component Interaction

1. **Initialization**: Validates `.env` settings via Pydantic and configures Hardware (USB HID Gadgets & Video Bridge).
2. **Build**: Compiles C++ and Go binaries if requested.
3. **Runtime**: Orchestrates `hid_server` and `mediamtx` as asynchronous subprocesses. `MediaMTX` triggers the `video_engine` pipeline via internal configuration.
4. **Shutdown**: Graceful termination of all subprocesses and resource cleanup via Context Managers.

## Usage

### Prerequisites
- Raspberry Pi 4 with TC358743 Video Bridge.
- Go, G++, and Python 3.10+ installed.

### Execution
Run the orchestrator (use `sudo` for hardware access):
```bash
# Build and start all services
python -m app.main run --build

# Start without rebuilding
python -m app.main run

# Send USB wakeup signal to host
python -m app.main wake
```

## Configuration
- `.env`: Environment variables (paths, device nodes).
- `config/config.json`: Video engine parameters (bitrate, resolution).
- `config/mediamtx.yml`: Streaming server and ffmpeg pipeline settings.
