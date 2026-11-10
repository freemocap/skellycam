"""Which USB generation a camera is connected through: "USB 3", "USB 2" or "USB 1".

Reported as a fact for the camera list and error messages; it says nothing about which settings
will work. Returns None whenever the connection cannot be determined, so camera detection never
fails because of it.

- Windows: the camera's DirectShow device path leads (Configuration Manager) to the USB device and
  the hub port it is attached to; the hub reports whether that port operates at SuperSpeed
  [@windowsUsbConnectionFlags] [@windowsCfgmgrDeviceAddress].
- Linux: the video4linux device's USB device reports its speed in sysfs [@linuxSysfsUsbSpeed].
- macOS: the AVFoundation unique ID of a USB camera begins with its USB location ID, and the
  IOUSBHostDevice with that location ID reports its connection speed [@macosIOUSBHostSpeed].
  Not yet verified on Mac hardware.
"""
import logging
import platform
import plistlib
import re
import struct
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

USB_HUB_INTERFACE = "{f18a0e88-c30c-11d0-8815-00a0c906bed8}"  # GUID_DEVINTERFACE_USB_HUB
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 0x220448
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2 = 0x22045C
CM_DRP_ADDRESS = 0x1D
OPERATING_AT_SUPERSPEED_OR_HIGHER = 0x1
WINDOWS_DEVICE_PATH = re.compile(
    r"^\\\\\?\\(?P<instance>usb#vid_(?P<vid>[0-9a-f]{4})&pid_(?P<pid>[0-9a-f]{4})[^#]*#[^#]+)#\{", re.IGNORECASE)
MACOS_USB_UNIQUE_ID = re.compile(r"0x(?P<location>[0-9a-f]{8})[0-9a-f]{8}", re.IGNORECASE)


def usb_version(device_path: str | None) -> str | None:
    """The USB generation of the camera at OpenCV/cv2_enumerate_cameras `device_path`, or None."""
    if not device_path:
        return None
    try:
        system = platform.system()
        if system == "Windows":
            return _windows_usb_version(device_path)
        if system == "Linux":
            return _linux_usb_version(device_path)
        if system == "Darwin":
            return _macos_usb_version(device_path)
    except Exception as error:  # a missing fact must not break camera detection
        logger.debug(f"USB connection of {device_path} unknown: {type(error).__name__} - {error}")
    return None


def usb_version_from_megabits(megabits_per_second: float | int) -> str:
    """Kernel sysfs speeds: 1.5/12 (USB 1), 480 (USB 2), 5000/10000/20000 (USB 3)."""
    if megabits_per_second >= 5000:
        return "USB 3"
    return "USB 2" if megabits_per_second >= 480 else "USB 1"


def usb_version_from_iokit_speed(speed: int | None) -> str | None:
    """tIOUSBHostConnectionSpeed: 1 full, 2 low, 3 high, 4 super, 5 super+, 6 super+ x2."""
    if speed is None or speed <= 0:
        return None
    if speed >= 4:
        return "USB 3"
    return "USB 2" if speed == 3 else "USB 1"


def _linux_usb_version(device_path: str, sys_root: Path = Path("/sys")) -> str | None:
    # /sys/class/video4linux/videoN/device is the USB interface; the USB device above it has `speed`.
    device = sys_root / "class" / "video4linux" / Path(device_path).name / "device"
    if not device.exists():
        return None
    resolved = device.resolve()
    for directory in (resolved, *resolved.parents):
        speed = directory / "speed"
        if speed.is_file():
            return usb_version_from_megabits(float(speed.read_text().strip()))
        if directory == sys_root:
            break
    return None


def _macos_usb_version(device_path: str) -> str | None:
    match = MACOS_USB_UNIQUE_ID.fullmatch(device_path)
    if not match:
        return None  # not a USB camera (built-in, Continuity or virtual)
    location = int(match.group("location"), 16)
    listing = subprocess.run(["ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-d", "1"],
                             capture_output=True, check=True, timeout=5).stdout
    for device in plistlib.loads(listing):
        if device.get("locationID") == location:
            return usb_version_from_iokit_speed(device.get("USBSpeed"))
    return None


def _windows_usb_version(device_path: str) -> str | None:
    import ctypes
    from ctypes import wintypes

    match = WINDOWS_DEVICE_PATH.match(device_path)
    if not match:
        return None  # not a USB camera (built-in PCI, network or virtual)
    vendor, product = int(match.group("vid"), 16), int(match.group("pid"), 16)
    cfgmgr = ctypes.WinDLL("cfgmgr32")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                         ctypes.c_void_p]
    invalid_handle = wintypes.HANDLE(-1).value

    def device_id(node: wintypes.DWORD) -> str:
        buffer = ctypes.create_unicode_buffer(512)
        if cfgmgr.CM_Get_Device_IDW(node, buffer, len(buffer), 0) != 0:
            raise OSError("CM_Get_Device_IDW failed")
        return buffer.value

    def ioctl(handle, code: int, payload: bytes, out_size: int) -> bytes:
        buffer = ctypes.create_string_buffer(payload, max(len(payload), out_size))
        returned = wintypes.DWORD()
        if not kernel32.DeviceIoControl(handle, code, buffer, len(payload), buffer, out_size,
                                        ctypes.byref(returned), None):
            raise OSError(ctypes.get_last_error(), f"DeviceIoControl 0x{code:X} failed")
        return buffer.raw[:returned.value]

    node = wintypes.DWORD()
    if cfgmgr.CM_Locate_DevNodeW(ctypes.byref(node), match.group("instance").replace("#", "\\"), 0) != 0:
        return None
    for _ in range(4):  # video interface -> USB device -> hub (composite devices add one level)
        parent = wintypes.DWORD()
        if cfgmgr.CM_Get_Parent(ctypes.byref(parent), node, 0) != 0:
            return None
        hub_path = "\\\\?\\" + device_id(parent).replace("\\", "#") + "#" + USB_HUB_INTERFACE
        hub = kernel32.CreateFileW(hub_path, 0x40000000, 0x2, None, 3, 0, None)  # GENERIC_WRITE, FILE_SHARE_WRITE, OPEN_EXISTING
        if hub == invalid_handle:
            node = parent  # not a hub: keep walking up
            continue
        try:
            address, length = wintypes.DWORD(), wintypes.ULONG(4)
            if cfgmgr.CM_Get_DevNode_Registry_PropertyW(node, CM_DRP_ADDRESS, None, ctypes.byref(address),
                                                        ctypes.byref(length), 0) != 0:
                return None
            port = address.value
            info = ioctl(hub, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX, struct.pack("<I", port) + b"\0" * 600, 604)
            port_vendor, port_product = struct.unpack_from("<HH", info, 12)
            if (port_vendor, port_product) != (vendor, product):
                return None  # the address did not identify this camera's port
            flags = struct.unpack_from("<I", ioctl(hub, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2,
                                                    struct.pack("<IIII", port, 16, 0x7, 0), 16), 12)[0]
            if flags & OPERATING_AT_SUPERSPEED_OR_HIGHER:
                return "USB 3"
            return {0: "USB 1", 1: "USB 1", 2: "USB 2", 3: "USB 3"}.get(info[23])
        finally:
            kernel32.CloseHandle(hub)
    return None
