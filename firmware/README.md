# front-panel firmware

**Firmware version:** 1.0  
**Protocol version:** 1  
**Platform:** RP2040-Zero (Waveshare) running MicroPython

## What it does

This firmware turns the RP2040-Zero into a UART-controlled front-panel adapter.
The board drives opto-isolated outputs to simulate Power/Reset button presses on
a target PC, and reads PWR_LED / HDD_LED states back to the host.

Communication with the Raspberry Pi 4 host (`kvm_engine_py`) happens over UART
at 115200 baud using a line-delimited JSON protocol.

Full protocol specification: [`docs/uart_protocol.md`](docs/uart_protocol.md)

## File layout

```
firmware/
├── docs/
│   └── uart_protocol.md   # communication contract (read this first)
├── src/
│   ├── main.py            # entry-point; runs automatically on boot
│   ├── config.py          # all pin numbers, durations, constants
│   ├── protocol.py        # JSON frame parsing / serialisation
│   ├── pulse.py           # non-blocking Timer-based pulse generator
│   ├── leds.py            # 5 ms sampler + 1500 ms window classifier
│   └── uart_handler.py    # UART accumulator + command dispatcher
└── tools/
    ├── flash_instructions.md  # how to flash the board via Thonny
    └── repl_test.py           # manual verification steps for REPL
```

## Quick start

See [`tools/flash_instructions.md`](tools/flash_instructions.md) for full
flashing instructions.  Short version:

1. Download MicroPython UF2 for RP2040 from https://micropython.org/download/RPI_PICO/
2. Enter bootloader (hold BOOTSEL → plug USB) and drag UF2 to the drive.
3. Open Thonny, select **MicroPython (Raspberry Pi Pico)** interpreter.
4. Upload all files from `firmware/src/` to the device root.
5. Reboot — `main.py` starts automatically.

## REPL / diagnostic mode

To import a module without starting the main loop:

```python
import config
config.AUTO_START = False
import main        # imports without starting run()
main.run()         # start manually when ready
```

Each module (`pulse`, `leds`, `protocol`) is independently importable and
testable from the REPL without running `main.py`.
