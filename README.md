# IP-KVM Orchestrator (Python-based)

A unified orchestrator for Raspberry Pi 4 IP-KVM, managing hardware-accelerated video streaming and HID emulation.

## Architecture Overview

The system follows an **Event-Driven Orchestrator** pattern, where Python acts as the "brain" managing high-performance components:

- **Hardware Layer (`app/hardware/`)**: Native Python implementation for Linux ConfigFS (USB Gadget) and V4L2 (Video Bridge) initialization. Replaces legacy Shell scripts. Includes optional front-panel module (`front_panel.py`) for RP2040-Zero UART integration.
- **Service Layer (`app/services/`)**: 
    - `ProjectBuilder`: Automated C++ (GCC) compiler orchestration.
    - `ServiceManager`: Asyncio-based lifecycle management for background processes.
- **WebSocket Layer (`app/ws/`)**: Single shared `WSServer` (aiohttp) listening on one port. All WebSocket routes (`/ws/control`, `/ws/front_panel`) are registered on it at startup. JWT-authenticated.
- **HID Layer (`app/hid/`)**: Keyboard and mouse emulation over HID gadget. Registers `/ws/control` on the shared `WSServer`; does not own the server lifecycle.
- **Execution Layer (`src/`)**:
    - `video_engine` (C++): Hardware-accelerated H.264 encoding via V4L2.
    - `MediaMTX`: High-efficiency WebRTC/RTSP streaming server.

## Component Interaction

1. **Initialization**: Validates `.env` settings via Pydantic and configures Hardware (USB HID Gadgets & Video Bridge).
2. **Build**: Compiles C++ and Go binaries if requested.
3. **Runtime**: Orchestrates `mediamtx`, the shared `WSServer`, HID logic, and the optional front-panel UART bridge as concurrent asyncio tasks inside a single `TaskGroup`. `MediaMTX` triggers the `video_engine` pipeline via internal configuration.
4. **Shutdown**: Graceful termination of all subprocesses and resource cleanup via Context Managers.

## Usage

### Prerequisites
- Raspberry Pi 4 with TC358743 Video Bridge.
- G++ and Python 3.10+ installed.

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

## Front-Panel Module (Optional)

An optional hardware add-on based on the RP2040-Zero microcontroller provides remote control of the target PC's front-panel connectors via UART.

**Capabilities:**
- Send Power/Reset button events (`power_press`, `power_hold`, `reset`)
- Read PWR\_LED and HDD\_LED states in real-time (`on`, `off`, `blinking`, `idle`, `active`, `unknown`)

**Hardware connection:** Raspberry Pi GPIO14/15 (UART0) ↔ RP2040-Zero GP0/GP1 at 115200 baud, 3.3 V TTL.

**Startup behavior:** At boot, `kvm_engine_py` probes the UART port with up to 5 ping attempts (exponential back-off: 200 → 3000 ms). If the board is not detected, the subsystem is disabled with a `WARN` log entry and all other services continue normally.

**Configuration** (via `config/config.json` or defaults):

| Key | Default | Description |
|---|---|---|
| `front_panel_enabled` | `true` | Set to `false` to skip probe entirely |
| `front_panel_port` | `/dev/ttyAMA0` | UART device path (Linux only) |
| `front_panel_baudrate` | `115200` | Baud rate |

On Windows / development machines without UART hardware, the probe fails gracefully — set `front_panel_enabled: false` in your config or run with the default (probe will time out and disable itself automatically).

**WebSocket API** (same port as HID, default `8080`):

```
ws://<host>:<hid_port>/ws/front_panel?token=<JWT>
```

Server → client frames:

| Frame | Description |
|---|---|
| `{"type":"led_status","pwr":"on","hdd":"idle"}` | LED state, ~10 Hz |
| `{"type":"ack","cmd":"power_press"}` | Command confirmed |
| `{"type":"error","reason":"not_connected"}` | Board unavailable |
| `{"type":"error","reason":"malformed_json"}` | Bad JSON from client |
| `{"type":"error","reason":"unknown_command","received":"..."}` | Unknown command |
| `{"type":"error","reason":"internal"}` | Unexpected server error |

Client → server frames: `{"type":"power_press"}`, `{"type":"power_hold"}`, `{"type":"reset"}`.

A slow client (send blocked > 1 s) is disconnected. Invalid or missing JWT → HTTP 401 before WebSocket upgrade.

Protocol details: `firmware/docs/uart_protocol.md`.

## Configuration
- `config/config.json`: Service parameters (paths, HID ports, front-panel settings).
- `config/mediamtx.yml`: Streaming server and ffmpeg pipeline settings.
