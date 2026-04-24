--

# Architecture Overview: IP-KVM Orchestrator

## 1. Concept
The project is transitioning from a collection of loosely coupled Bash scripts to a unified **Event-Driven Orchestrator** written in Python. Python acts as the "brain," managing the lifecycle of high-performance components written in C++ and Go.



## 2. Core Principles
* **SOLID & SRP:** Each module has a single responsibility (e.g., Hardware Init, Service Management, Building).
* **Infrastructure as Code:** Hardware configuration (USB Gadgets, V4L2) is handled natively via Python's `pathlib` and `os` instead of shell wrappers.
* **Resilience:** Use of **Asyncio Context Managers** ensures that if one component fails or the system stops, all resources (subprocesses, memory, file handles) are cleaned up.
* **Observability:** Structured logging with `structlog` provides JSON for `systemd` and human-readable output for terminal debugging.

---

## 3. System Layers

### A. Configuration Layer
* **`.env`**: Local environment variables (GPIO pins, file paths).
* **`app/config.py`**: **Pydantic Settings** model that validates the `.env` file at startup. It ensures all required paths and integers are valid before the code execution starts.

### B. Management Layer (The Orchestrator)
* **`MainApp` (app/main.py)**: The entry point using `click`. Handles CLI arguments (`--build`, `--debug`) and initializes the global logger.
* **`ServiceManager` (app/services/manager.py)**: Manages the lifecycle of background processes (`mediamtx`, `hid_server`, `kvm_engine`). It monitors their state and handles graceful shutdowns.
* **`ProjectBuilder` (app/services/builder.py)**: Handles automated compilation of C++ and Go binaries and manages external C++ dependencies (e.g., `nlohmann/json`).
* **`HardwareManager` (app/hardware/...)**: Directly interacts with Linux ConfigFS and V4L2 to initialize the USB Gadget and Video Bridge.

### C. Execution Layer (Workers)
* **`MediaMTX` (Go)**: High-efficiency video streaming (WebRTC/RTSP).
* **`HIDServer` (Python/asyncio)**: Real-time HID emulation over WebSockets — integrated directly into `kvm_engine_py` via `app.hid.server`.
* **`KVM Engine` (C++)**: Low-latency hardware-accelerated video encoding.

---

## 4. Component Interaction Flow

1.  **Systemd/CLI**: Executes `python -m app.main`.
2.  **Initialization**: 
    * Load and validate `Settings`.
    * Setup `structlog` (detects TTY for coloring).
3.  **Bootstrap**: 
    * If `--build`: `ProjectBuilder` checks/compiles binaries.
    * `HardwareManager`: Configures USB HID Gadget and TC358743 Video Bridge.
4.  **Runtime**: 
    * `ServiceManager` starts `hid_server` and `mediamtx` as asynchronous subprocesses.
    * `StatusIndicator` updates the RGB LED to **Green (Idle)**.
5.  **Termination**: 
    * On `SIGTERM` or `Ctrl+C`, the orchestrator shuts down all subprocesses gracefully via Context Managers.

---

## 5. Technology Stack
| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.10+ |
| **CLI Framework** | `click` |
| **Validation** | `pydantic`, `pydantic-settings` |
| **Logging** | `structlog` |
| **I/O** | `asyncio`, `aiohttp` (WebSocket), `httpx` (downloads) |
| **Environment** | `venv` (Isolated Virtual Environment) |

---
