import os
import shutil
import subprocess
from pathlib import Path
import structlog
import asyncio

log = structlog.get_logger()

class HardwareManager:
    def __init__(self, settings):
        self.settings = settings
        self.configfs_home = Path("/sys/kernel/config/usb_gadget")
        self.gadget_name = "kvm_gadget"
        self.gadget_path = self.configfs_home / self.gadget_name

    def setup_usb_gadget(self):
        """Ported logic from setup_usb_gadget.sh"""
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
        self._create_hid_function("hid.usb0", 1, 1, 8, bytes.fromhex("05010906a101050719e029e71500250175019508810295017508810395057501050819012905910295017503910395067508150025650507190029658100c0"))
        self._create_hid_function("hid.usb1", 2, 1, 4, bytes.fromhex("05010902a1010901a1000509190129031500250195037501810295017505810305010930093109381581257f750895038106c0c0"))

        # 6. Create Configuration
        config_path = self.gadget_path / "configs" / "c.1"
        config_strings_path = config_path / "strings" / "0x409"
        config_strings_path.mkdir(parents=True, exist_ok=True)
        (config_strings_path / "configuration").write_text("Config 1: HID Gadget")
        (config_path / "bmAttributes").write_text("0xa0")
        (config_path / "MaxPower").write_text("250")

        # 7. Bind Functions
        (config_path / "hid.usb0").symlink_to(self.gadget_path / "functions" / "hid.usb0")
        (config_path / "hid.usb1").symlink_to(self.gadget_path / "functions" / "hid.usb1")

        # 8. Enable Gadget
        udc_controllers = os.listdir("/sys/class/udc")
        if not udc_controllers:
            log.error("hardware_no_udc_found")
            return
        
        udc_name = udc_controllers[0]
        (self.gadget_path / "UDC").write_text(udc_name)
        log.info("hardware_gadget_enabled", udc=udc_name)

    def _create_hid_function(self, name, protocol, subclass, report_length, report_desc):
        func_path = self.gadget_path / "functions" / name
        func_path.mkdir(parents=True, exist_ok=True)
        (func_path / "protocol").write_text(str(protocol))
        (func_path / "subclass").write_text(str(subclass))
        (func_path / "report_length").write_text(str(report_length))
        (func_path / "report_desc").write_bytes(report_desc)

    def _cleanup_gadget(self):
        log.info("hardware_gadget_cleanup")
        # Unbind UDC
        udc_file = self.gadget_path / "UDC"
        if udc_file.exists():
            try:
                udc_file.write_text("\n")
            except OSError:
                pass

        # Remove symlinks in configs
        config_path = self.gadget_path / "configs" / "c.1"
        if config_path.exists():
            for link in ["hid.usb0", "hid.usb1"]:
                link_path = config_path / link
                if link_path.exists():
                    link_path.unlink()
            
            # Remove config strings and config dir
            shutil.rmtree(config_path / "strings" / "0x409", ignore_errors=True)
            try:
                config_path.rmdir()
            except OSError:
                pass

        # Remove functions
        functions_path = self.gadget_path / "functions"
        if functions_path.exists():
            for func in ["hid.usb0", "hid.usb1"]:
                func_dir = functions_path / func
                if func_dir.exists():
                    try:
                        func_dir.rmdir()
                    except OSError:
                        pass
        
        # Remove top strings and gadget dir
        shutil.rmtree(self.gadget_path / "strings" / "0x409", ignore_errors=True)
        try:
            self.gadget_path.rmdir()
        except OSError:
            pass

    async def init_v4l2(self):
        """Ported logic from init_kvm.sh"""
        log.info("hardware_v4l2_init", device=self.settings.video_device)
        
        # 1. Load EDID
        if self.settings.edid_path.exists():
            # Use raw format for v4l2-ctl if needed, init_kvm.sh says format=raw
            subprocess.run(["v4l2-ctl", "-d", self.settings.video_device, "--set-edid", f"pad=0,file={self.settings.edid_path},format=raw"], check=True)
        else:
            log.warning("hardware_edid_missing", path=str(self.settings.edid_path))

        # 2. Wait for stable video signal
        log.info("hardware_v4l2_waiting_signal")
        while True:
            try:
                result = subprocess.run(
                    ["v4l2-ctl", "-d", self.settings.video_device, "--query-dv-timings"],
                    capture_output=True, text=True, check=False
                )
                if "Active width" in result.stdout:
                    width_line = [line for line in result.stdout.split('\n') if "Active width" in line]
                    if width_line:
                        width_val = width_line[0].split(':')[1].strip()
                        if int(width_val) > 0:
                            break
            except Exception:
                pass
            await asyncio.sleep(1)

        # 3. Query DV timings
        subprocess.run(["v4l2-ctl", "-d", self.settings.video_device, "--set-dv-bt-timings", "query"], check=False)

        # 4. Get detected resolution
        result = subprocess.run(
            ["v4l2-ctl", "-d", self.settings.video_device, "--query-dv-timings"],
            capture_output=True, text=True, check=False
        )
        
        width = 1280
        height = 720
        for line in result.stdout.split('\n'):
            if "Active width" in line:
                width = int(line.split(':')[1].strip())
            elif "Active height" in line:
                height = int(line.split(':')[1].strip())

        # 5. Set pixel format and resolution
        subprocess.run([
            "v4l2-ctl", "-d", self.settings.video_device, 
            f"--set-fmt-video=width={width},height={height},pixelformat=UYVY"
        ], check=True)
        
        log.info("hardware_v4l2_complete", resolution=f"{width}x{height}")

    def wake_host(self):
        """Ported logic from wake_host.sh"""
        log.info("hardware_wake_host_signal")
        
        # Try USB SRP (Session Request Protocol)
        udc_controllers = os.listdir("/sys/class/udc")
        if udc_controllers:
            udc_name = udc_controllers[0]
            srp_path = Path(f"/sys/class/udc/{udc_name}/srp")
            if srp_path.exists():
                try:
                    srp_path.write_text("1")
                except OSError:
                    pass

        # Send Left Shift keypress
        hid_path = Path("/dev/hidg0")
        if hid_path.exists():
            try:
                # Left Shift press
                hid_path.write_bytes(bytes([0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
                import time
                time.sleep(0.1)
                # Release
                hid_path.write_bytes(bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
                log.info("hardware_wake_host_sent")
            except Exception as e:
                log.error("hardware_wake_host_failed", error=str(e))
        else:
            log.warning("hardware_hid_missing_for_wake", path=str(hid_path))

