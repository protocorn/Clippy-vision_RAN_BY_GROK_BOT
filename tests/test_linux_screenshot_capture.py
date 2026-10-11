"""Linux screenshot session detection, blank-frame guard, and Xvfb capture."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import pytest
from PIL import Image

from core.linux_screenshot import (
    grab_linux_screen,
    image_is_blank_or_black,
    linux_session_type,
    reset_linux_screenshot_warnings,
)


class TestLinuxSessionDetection(unittest.TestCase):
    @pytest.mark.linux
    def test_session_x11_from_env(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, clear=False):
            self.assertEqual(linux_session_type(), "x11")

    @pytest.mark.linux
    def test_session_wayland_from_xdg(self):
        with patch.dict(
            os.environ,
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-1"},
            clear=False,
        ):
            self.assertEqual(linux_session_type(), "wayland")

    @pytest.mark.linux
    def test_session_wayland_from_wayland_display(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_SESSION_TYPE"}
        env["WAYLAND_DISPLAY"] = "wayland-0"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(linux_session_type(), "wayland")


class TestBlankFrameGuard(unittest.TestCase):
    @pytest.mark.linux
    def test_detects_all_black(self):
        img = Image.new("RGB", (100, 80), (0, 0, 0))
        self.assertTrue(image_is_blank_or_black(img))

    @pytest.mark.linux
    def test_accepts_colored_frame(self):
        img = Image.new("RGB", (100, 80), (40, 120, 200))
        self.assertFalse(image_is_blank_or_black(img))


class TestGrabLinuxScreen(unittest.TestCase):
    @pytest.mark.linux
    @patch("core.linux_screenshot._grab_via_mss")
    @patch("core.linux_screenshot.linux_session_type", return_value="wayland")
    def test_wayland_blank_mss_skips(self, _session, mock_mss):
        reset_linux_screenshot_warnings()
        mock_mss.return_value = (Image.new("RGB", (10, 10), (0, 0, 0)), {"left": 0, "top": 0, "width": 10, "height": 10})
        with patch.dict(os.environ, {"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"}, clear=False):
            with patch("builtins.print") as mock_print:
                self.assertIsNone(grab_linux_screen(False))
                stderr_calls = [c for c in mock_print.call_args_list if c.kwargs.get("file") is sys.stderr]
                self.assertTrue(stderr_calls)

    @pytest.mark.linux
    @patch("core.linux_screenshot._grab_via_mss")
    @patch("core.linux_screenshot.linux_session_type", return_value="x11")
    def test_x11_non_blank_mss_returns(self, _session, mock_mss):
        img = Image.new("RGB", (64, 48), (10, 20, 30))
        monitor = {"left": 0, "top": 0, "width": 64, "height": 48}
        mock_mss.return_value = (img, monitor)
        with patch.dict(os.environ, {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}, clear=False):
            with patch("core.linux_screenshot._active_window_rect", return_value=None):
                result = grab_linux_screen(False)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].size, (64, 48))

    @pytest.mark.linux
    @patch("core.linux_screenshot.linux_session_type", return_value="wayland")
    def test_wayland_without_display_warns(self, _session):
        reset_linux_screenshot_warnings()
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
        env["XDG_SESSION_TYPE"] = "wayland"
        env["WAYLAND_DISPLAY"] = "wayland-1"
        with patch.dict(os.environ, env, clear=True):
            with patch("shutil.which", return_value=None):
                with patch("builtins.print") as mock_print:
                    self.assertIsNone(grab_linux_screen(False))
                    stderr_calls = [c for c in mock_print.call_args_list if c.kwargs.get("file") is sys.stderr]
                    self.assertTrue(stderr_calls)


def _spawn_xvfb_fixture_window() -> subprocess.Popen | None:
    """Draw a visible window so mss has non-black pixels under Xvfb."""
    try:
        proc = subprocess.Popen(
            [
                "xterm",
                "-bg",
                "#336699",
                "-fg",
                "white",
                "-geometry",
                "240x160+24+24",
                "-e",
                "sleep",
                "90",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.6)
        return proc
    except (OSError, subprocess.SubprocessError):
        return None


@pytest.mark.linux
@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only Xvfb capture test")
def test_x11_screenshot_non_blank_under_xvfb():
    """Real grab under Xvfb; CI runs this step with xvfb-run."""
    if not os.environ.get("DISPLAY"):
        pytest.skip("DISPLAY not set (run under xvfb-run)")

    fixture = _spawn_xvfb_fixture_window()
    if fixture is None:
        pytest.skip("xterm not available for Xvfb fixture")

    reset_linux_screenshot_warnings()
    with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}, clear=False):
        result = grab_linux_screen(capture_all_monitors=True)
    assert result is not None
    img, monitor = result
    assert img.width >= 1 and img.height >= 1
    assert monitor["width"] == img.width
    assert monitor["height"] == img.height
    assert not image_is_blank_or_black(img)
    fixture.terminate()


@pytest.mark.linux
@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only scheduler integration")
def test_capture_screenshot_integration_under_xvfb():
    if not os.environ.get("DISPLAY"):
        pytest.skip("DISPLAY not set (run under xvfb-run)")

    from pathlib import Path
    from unittest.mock import patch

    from core import screenshot_files
    from core import screenshot_scheduler as scheduler

    reset_linux_screenshot_warnings()
    fixture = _spawn_xvfb_fixture_window()
    if fixture is None:
        pytest.skip("xterm not available for Xvfb fixture")
    settings = {
        "capture_screenshots": True,
        "capture_all_monitors": True,
        "min_gap_seconds": 0,
        "capture_clipboard": False,
    }
    metadata = {
        "timestamp": 0.0,
        "current_window_title": "test",
        "active_url": None,
        "process_name": "xvfb",
    }
    with patch.object(scheduler, "get_capture_settings", return_value=settings), patch.object(
        scheduler, "get_window_metadata", return_value=metadata
    ), patch.object(scheduler, "should_watch_process", return_value=True), patch.object(
        scheduler, "_redact_clippy_windows"
    ), patch.object(scheduler, "save_crop_metadata"), patch(
        "core.editor_accessibility.ensure_screen_reader_support"
    ), patch.object(screenshot_files, "write_frame_window"):
        path = scheduler.capture_screenshot(999_001)
    fixture.terminate()
    assert path is not None
    assert Path(path).is_file()
    img = Image.open(path)
    assert not image_is_blank_or_black(img.convert("RGB"))
    path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
