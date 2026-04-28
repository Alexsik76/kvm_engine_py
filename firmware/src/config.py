# UART
UART_ID   = 0
UART_TX   = 0   # GP0
UART_RX   = 1   # GP1
UART_BAUD = 115200

# Output pins (optocoupler control)
PWR_BTN_PIN = 2  # GP2
RST_BTN_PIN = 3  # GP3

# Input pins (LED sense via optocouplers)
PWR_LED_PIN = 4  # GP4
HDD_LED_PIN = 5  # GP5

# Pulse durations (ms)
POWER_PRESS_MS = 100
POWER_HOLD_MS  = 6000
RESET_MS       = 100

# LED sampling
SAMPLE_INTERVAL_MS = 5
WINDOW_MS          = 1500
WINDOW_SIZE        = WINDOW_MS // SAMPLE_INTERVAL_MS  # 300 samples

# Streaming
LED_STATUS_INTERVAL_MS = 100

# Protocol / firmware identity
FW_VERSION       = "1.0"
PROTOCOL_VERSION = 1
MAX_FRAME_BYTES  = 256  # inclusive of terminating \n

# Logging: "DEBUG" | "INFO" | "ERROR"
LOG_LEVEL = "DEBUG"

# Set to False before importing main.py from REPL to suppress auto-start
AUTO_START = True

# ---------------------------------------------------------------------------
_LEVELS = {"DEBUG": 0, "INFO": 1, "ERROR": 2}

def log(level, msg):
    if _LEVELS.get(level, 99) >= _LEVELS.get(LOG_LEVEL, 1):
        print("[{}] {}".format(level, msg))
