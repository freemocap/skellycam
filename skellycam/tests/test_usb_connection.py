"""Each platform's USB connection lookup reports 'USB 3', 'USB 2', 'USB 1' or None, never an error."""
import plistlib
from types import SimpleNamespace

import pytest

from skellycam.core.device_detection import usb_connection as connection


@pytest.mark.parametrize(("megabits", "expected"), [(1.5, "USB 1"), (12, "USB 1"), (480, "USB 2"),
                                                    (5000, "USB 3"), (10000, "USB 3"), (20000, "USB 3")])
def test_linux_speeds_map_to_usb_generations(megabits, expected):
    assert connection.usb_version_from_megabits(megabits) == expected


@pytest.mark.parametrize(("speed", "expected"), [(0, None), (1, "USB 1"), (2, "USB 1"), (3, "USB 2"),
                                                 (4, "USB 3"), (5, "USB 3"), (6, "USB 3"), (None, None)])
def test_iokit_speeds_map_to_usb_generations(speed, expected):
    assert connection.usb_version_from_iokit_speed(speed) == expected


def test_linux_reads_the_speed_of_the_usb_device_above_the_video_interface(tmp_path):
    camera = tmp_path / "class" / "video4linux" / "video2"
    (camera / "device").mkdir(parents=True)
    (camera / "speed").write_text("480\n")
    assert connection._linux_usb_version("/dev/video2", sys_root=tmp_path) == "USB 2"
    assert connection._linux_usb_version("/dev/video9", sys_root=tmp_path) is None


def test_macos_matches_the_location_id_in_the_avfoundation_unique_id(monkeypatch):
    listing = plistlib.dumps([{"locationID": 0x14100000, "USBSpeed": 4}, {"locationID": 0x14200000, "USBSpeed": 3}])
    monkeypatch.setattr(connection.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=listing))
    assert connection._macos_usb_version("0x14200000046d0825") == "USB 2"
    assert connection._macos_usb_version("0x14100000046d0825") == "USB 3"
    assert connection._macos_usb_version("FaceTime HD Camera") is None


def test_windows_device_paths_parse_and_non_usb_paths_are_unknown():
    match = connection.WINDOWS_DEVICE_PATH.match(
        r"\\?\usb#vid_32e4&pid_5234&mi_00#6&fadbf3b&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global")
    assert match.group("instance") == r"usb#vid_32e4&pid_5234&mi_00#6&fadbf3b&0&0000"
    assert (match.group("vid"), match.group("pid")) == ("32e4", "5234")
    assert connection.WINDOWS_DEVICE_PATH.match(r"\\?\root#image#0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}") is None


def test_lookup_failures_report_unknown_instead_of_raising(monkeypatch):
    monkeypatch.setattr(connection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(connection, "_linux_usb_version", lambda path: (_ for _ in ()).throw(OSError("no sysfs")))
    assert connection.usb_version("/dev/video0") is None
    assert connection.usb_version(None) is None
