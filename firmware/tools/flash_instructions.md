# Flashing RP2040-Zero — Step-by-Step

## 1. Download MicroPython

Go to https://micropython.org/download/RPI_PICO/ and download the latest
`.uf2` file for **Raspberry Pi Pico / RP2040**.

## 2. Enter bootloader mode

1. Hold the **BOOTSEL** button on the RP2040-Zero.
2. While holding, connect the board to your PC via USB.
3. Release BOOTSEL — the board mounts as a USB flash drive (e.g. `RPI-RP2`).

## 3. Install MicroPython

Drag-and-drop the downloaded `.uf2` file onto the `RPI-RP2` drive.
The drive will disappear and the board will reboot into MicroPython.

## 4. Install Thonny

Download and install **Thonny** from https://thonny.org.

In Thonny:
- Go to **Tools → Options → Interpreter**.
- Select **MicroPython (Raspberry Pi Pico)**.
- Choose the correct COM port (or leave on Auto-detect).

## 5. Upload firmware files

In Thonny's file panel (left side), right-click each file from `firmware/src/`
and choose **"Upload to / (MicroPython device)"**:

```
config.py
protocol.py
pulse.py
leds.py
uart_handler.py
main.py
```

The files must be uploaded to the **root** of the device (not a subdirectory),
so that `import config` etc. works without path manipulation.

## 6. Reboot and verify

Press the RESET button (or power-cycle) — `main.py` runs automatically.

You should see in Thonny's REPL:
```
[INFO] front-panel firmware v1.0 starting
[INFO] LED sampling started (window=1500ms)
[INFO] ready, waiting for ping
```

## 7. Manual REPL smoke-test

To test without running `main.py`, open a REPL session in Thonny and run:

```python
import config; config.AUTO_START = False
import pulse
pulse.start_pulse(2, 100)   # GP2 high for 100 ms → power button press simulation
```

GP2 should go high briefly (LED on optocoupler or oscilloscope confirms it).

See `tools/repl_test.py` for a full set of manual checks.
