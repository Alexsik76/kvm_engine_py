import time
from machine import UART, Pin
import config
import leds
import indicator
from uart_handler import UartHandler


def run():
    uart = UART(
        config.UART_ID,
        baudrate=config.UART_BAUD,
        tx=Pin(config.UART_TX),
        rx=Pin(config.UART_RX),
    )

    handler = UartHandler()
    handler.init(uart)
    leds.start_sampling()

    BLUE  = (0, 0, 10)
    GREEN = (0, 10, 0)
    OFF   = (0, 0, 0)

    PULSE_MS = 80
    GAP_MS   = 80

    indicator.set_color(*BLUE)

    streaming_enabled = False
    last_led_send     = time.ticks_ms()

    blink_active   = False
    blink_phase    = 0
    blink_phase_ts = 0

    while True:
        now = time.ticks_ms()

        if handler.poll():
            if not streaming_enabled:
                streaming_enabled = True
                last_led_send = now
            if not blink_active:
                blink_active   = True
                blink_phase    = 0
                blink_phase_ts = now
                indicator.set_color(*GREEN)

        if blink_active:
            duration = PULSE_MS if blink_phase % 2 == 0 else GAP_MS
            if time.ticks_diff(now, blink_phase_ts) >= duration:
                blink_phase += 1
                blink_phase_ts = now
                if blink_phase >= 6:
                    blink_active = False
                    indicator.set_color(*BLUE)
                elif blink_phase % 2 == 0:
                    indicator.set_color(*GREEN)
                else:
                    indicator.set_color(*OFF)

        if streaming_enabled:
            if time.ticks_diff(now, last_led_send) >= config.LED_STATUS_INTERVAL_MS:
                status = leds.get_status()
                handler.send({
                    "type": "led_status",
                    "pwr":  status["pwr"],
                    "hdd":  status["hdd"],
                })
                last_led_send = now


if config.AUTO_START:
    run()