import asyncio
import os
import shutil
import time
from pathlib import Path
import structlog
from app.config import Settings

log = structlog.get_logger()

# HID report descriptors (USB HID spec 1.11)
_KEYBOARD_REPORT_DESC = bytes.fromhex(
    "05010906a101050719e029e71500250175019508810295017508810395057501"
    "050819012905910295017503910395067508150025650507190029658100c0"
)
_MOUSE_REPORT_DESC = bytes.fromhex(
    "05010902a1010901a1000509190129031500250195037501810295017505810305010930"
    "093109381581257f750895038106c0c0"
)


class HardwareManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.configfs_home = Path("/sys/kernel/config/usb_gadget")
        self.gadget_name = "kvm_gadget"
        self.gadget_path = self.configfs_home / self.gadget_name

    def setup_usb_gadget(self):
        """Configures Linux USB Gadget via ConfigFS (ported from setup_usb_gadget.sh)."""
        if not self.configfs_home.exists():
            raise RuntimeError(f"configfs not mounted at {self.configfs_home}")

        if self.gadget_path.exists():
            self._cleanup_gadget()

        log.info("hardware_gadget_init", path=str(self.gadget_path))
        self.gadget_path.mkdir(parents=True, exist_ok=True)

        # 2. Set Device IDs
        (self.gadget_path / "idVendor").write_text("0x1d6b")
        (self.gadget_path / "idProduct").write_text("0x0104")
        (self.gadget_path / "bcdDevice").write_text("0x0100")
        (self.gadget_path / "bcdUSB").write_text("0x0200")

        # 3. Set Device Strings
        strings_path = self.gadget_path / "strings" / "0x409"
        strings_path.mkdir(parents=True, exist_ok=True)
        (strings_path / "serialnumber").write_text("6b626d001")
        (strings_path / "manufacturer").write_text("KVM Project")
        (strings_path / "product").write_text("KVM HID Interface")

        # 4. Create HID Functions
        self._create_hid_function("hid.usb0", protocol=1, subclass=1, report_length=8,  report_desc=_KEYBOARD_REPORT_DESC)
        self._create_hid_function("hid.usb1", protocol=2, subclass=1, report_length=4,  report_desc=_MOUSE_REPORT_DESC)

        # 5. Create Configuration
        config_path = self.gadget_path / "configs" / "c.1"
        config_strings_path = config_path / "strings" / "0x409"
        config_strings_path.mkdir(parents=True, exist_ok=True)
        (config_strings_path / "configuration").write_text("Config 1: HID Gadget")
        # bmAttributes: 0xe0 = Self-powered + Remote Wakeup
        (config_path / "bmAttributes").write_text("0xe0")
        # MaxPower: 0 = Pi has its own PSU, draws nothing from host
        (config_path / "MaxPower").write_text("0")

        # 6. Bind Functions
        (config_path / "hid.usb0").symlink_to(self.gadget_path / "functions" / "hid.usb0")
        (config_path / "hid.usb1").symlink_to(self.gadget_path / "functions" / "hid.usb1")

        # 7. Enable Gadget
        udc_controllers = os.listdir("/sys/class/udc")
        if not udc_controllers:
            log.error("hardware_no_udc_found")
            return

        udc_name = udc_controllers[0]
        (self.gadget_path / "UDC").write_text(udc_name)
        log.info("hardware_gadget_enabled", udc=udc_name)

    def _create_hid_function(self, name: str, protocol: int, subclass: int, report_length: int, report_desc: bytes):
        func_path = self.gadget_path / "functions" / name
        func_path.mkdir(parents=True, exist_ok=True)
        (func_path / "protocol").write_text(str(protocol))
        (func_path / "subclass").write_text(str(subclass))
        (func_path / "report_length").write_text(str(report_length))
        (func_path / "report_desc").write_bytes(report_desc)

    def _cleanup_gadget(self):
        log.info("hardware_gadget_cleanup")

        udc_file = self.gadget_path / "UDC"
        if udc_file.exists():
            try:
                udc_file.write_text("\n")
            except OSError as e:
                log.warning("hardware_gadget_udc_unbind_failed", error=str(e))

        config_path = self.gadget_path / "configs" / "c.1"
        if config_path.exists():
            for link in ["hid.usb0", "hid.usb1"]:
                link_path = config_path / link
                if link_path.exists():
                    link_path.unlink()
            shutil.rmtree(config_path / "strings" / "0x409", ignore_errors=True)
            try:
                config_path.rmdir()
            except OSError as e:
                log.warning("hardware_gadget_config_rmdir_failed", error=str(e))

        functions_path = self.gadget_path / "functions"
        if functions_path.exists():
            for func in ["hid.usb0", "hid.usb1"]:
                func_dir = functions_path / func
                if func_dir.exists():
                    try:
                        func_dir.rmdir()
                    except OSError as e:
                        log.warning("hardware_gadget_func_rmdir_failed", func=func, error=str(e))
            try:
                functions_path.rmdir()
            except OSError as e:
                log.warning("hardware_gadget_functions_rmdir_failed", error=str(e))

        shutil.rmtree(self.gadget_path / "strings" / "0x409", ignore_errors=True)
        try:
            self.gadget_path.rmdir()
        except OSError as e:
            log.warning("hardware_gadget_rmdir_failed", error=str(e))

    async def init_v4l2(self):
        """Initialises TC358743 video bridge (ported from init_kvm.sh)."""
        log.info("hardware_v4l2_init", device=self.settings.video_device)

        # 1. Load EDID so the host sees a monitor
        if self.settings.edid_path.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "v4l2-ctl", "-d", self.settings.video_device,
                    "--set-edid", f"pad=0,file={self.settings.edid_path},format=raw",
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(f"v4l2-ctl --set-edid exited with {proc.returncode}")
                log.info("hardware_edid_loaded")
            except Exception as e:
                log.warning("hardware_edid_failed", error=str(e))
        else:
            log.warning("hardware_edid_missing", path=str(self.settings.edid_path))

        # 2. Check for signal once (don't block waiting for it)
        log.info("hardware_v4l2_checking_signal")
        proc = await asyncio.create_subprocess_exec(
            "v4l2-ctl", "-d", self.settings.video_device, "--query-dv-timings",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, _ = await proc.communicate()
        stdout = stdout_bytes.decode(errors="replace")

        has_signal = "Active width" in stdout

        if has_signal:
            log.info("hardware_v4l2_signal_found")
            proc = await asyncio.create_subprocess_exec(
                "v4l2-ctl", "-d", self.settings.video_device,
                "--set-dv-bt-timings", "query",
            )
            await proc.wait()
        else:
            log.info("hardware_v4l2_no_signal_yet", message="Starting services anyway to allow HID wake")

        # 3. Parse detected resolution (fall back to 1280×720)
        width, height = 1280, 720
        if has_signal:
            for line in stdout.split("\n"):
                try:
                    if "Active width" in line:
                        width = int(line.split(":")[1].strip())
                    elif "Active height" in line:
                        height = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass

        # 4. Apply video format
        try:
            proc = await asyncio.create_subprocess_exec(
                "v4l2-ctl", "-d", self.settings.video_device,
                f"--set-fmt-video=width={width},height={height},pixelformat=UYVY",
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"v4l2-ctl --set-fmt-video exited with {proc.returncode}")
            log.info("hardware_v4l2_initialized", resolution=f"{width}x{height}")
        except Exception as e:
            log.error("hardware_v4l2_fmt_failed", error=str(e))

    def force_rebind_gadget(self):
        """Forces a virtual USB unplug/replug to recover from endpoint-shutdown states."""
        udc_controllers = os.listdir("/sys/class/udc")
        if not udc_controllers:
            return

        udc_name = udc_controllers[0]
        udc_file = self.gadget_path / "UDC"

        try:
            log.info("hardware_gadget_rebind_start", udc=udc_name)
            udc_file.write_text("\n")
            time.sleep(0.5)
            udc_file.write_text(udc_name)
            log.info("hardware_gadget_rebind_complete")
        except Exception as e:
            log.error("hardware_gadget_rebind_failed", error=str(e))

    def wake_host(self):
        log.info("hardware_wake_host_magic_sequence_start")
        self.force_rebind_gadget()
        log.info("hardware_wake_host_magic_sequence_complete")
