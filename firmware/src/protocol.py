import json
import config


def check_frame_length(line):
    """Return True if the raw line (without \\n) fits within MAX_FRAME_BYTES including the terminator."""
    return len((line + "\n").encode("utf-8")) <= config.MAX_FRAME_BYTES


def parse_frame(line):
    """Parse one JSON line. Returns dict on success, None on malformed input."""
    try:
        return json.loads(line.strip())
    except Exception:
        return None


def format_frame(obj):
    """Serialise dict to a JSON line terminated with \\n."""
    return json.dumps(obj) + "\n"
