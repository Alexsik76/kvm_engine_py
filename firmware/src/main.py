import time
from machine import UART, Pin
import config
import leds
from uart_handler import UartHandler


def run():
    config.log("INFO", "front-panel firmware v{} starting".format(config.FW_VERSION))

    uart = UART(
        config.UART_ID,
        baudrate=config.UART_BAUD,
        tx=Pin(config.UART_TX),
        rx=Pin(config.UART_RX),
    )

    handler = UartHandler()
    handler.init(uart)

    # Step 1: outputs already driven low by pulse.py on import (safe state).
    # Step 2: start LED sampler.
    leds.start_sampling()

    # Steps 3-4: listen for UART, send nothing until first ping.
    streaming_enabled = False
    last_led_send     = time.ticks_ms()

    config.log("INFO", "ready, waiting for ping")

    while True:
        # Step 5: poll() returns True once after ping/pong; enable streaming.
        if handler.poll() and not streaming_enabled:
            streaming_enabled = True
            config.log("INFO", "streaming enabled")
            last_led_send = time.ticks_ms()

        if streaming_enabled:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_led_send) >= config.LED_STATUS_INTERVAL_MS:
                status = leds.get_status()
                handler.send({
                    "type": "led_status",
                    "pwr":  status["pwr"],
                    "hdd":  status["hdd"],
                })
                last_led_send = now


# Guard: importing main.py from REPL without auto-start:
#   import config; config.AUTO_START = False; import main
if config.AUTO_START:
    run()
