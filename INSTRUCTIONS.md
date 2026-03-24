# Project Development Guidelines

## 1. Technical Stack & Libraries
Always prioritize and use the following libraries for Python development:
- **CLI:** `click`
- **Configuration & Validation:** `pydantic`, `pydantic_settings`, `python-dotenv`
- **Async HTTP:** `httpx`
- **Logging:** `structlog` (Structured logging)
- **Concurrency:** `asyncio`
- **Resource Management:** Context Managers (`@contextmanager`, `@asynccontextmanager`)

## 2. Coding Standards
- **Data Containers:** Use `dataclasses` (specifically `@dataclass`) for structured data instead of raw dictionaries where appropriate.
- **Formatting:** Adhere to PEP8 standards.
- **Documentation:** - No comments in Ukrainian. Use English for all code comments and docstrings.
    - Add comments ONLY for non-obvious logic or complex hardware interactions. Avoid trivial comments like `# Main loop`.
- **Architecture:** - Follow SOLID and SRP (Single Responsibility Principle).
    - Logic should be modularized (Hardware, Services, Orchestration).

## 3. Operational Requirements
- **Execution:** The entry point (`main.py`) must be compatible with `systemd` (running as a background service).
- **Logging Behavior:** - Use `structlog` to detect if the output is a TTY.
    - Provide human-readable, colored output for console/terminal execution.
    - Provide machine-readable (JSON) output when running under `systemctl` (non-TTY).
- **Environment:** Use `.env` files for local configuration, validated via Pydantic.
- **Dependency Management:** Use `venv` for isolation; never suggest system-wide package installation.

## 4. Hardware Specifics (Raspberry Pi)
- Prefer native Python implementations (using `pathlib`, `os`, `fcntl`) over wrapping Shell scripts (`.sh`).
- Use `subprocess` only for external binary execution (e.g., `mediamtx`, `g++`, `go build`).