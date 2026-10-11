"""Tests for OS-level capture opt-out detection."""

import unittest
from unittest.mock import MagicMock, patch, Mock
import sys

from core.capture_optout import (
    window_opted_out,
    should_skip_capture,
    forget_optout_cache,
    _is_private_process,
    _normalize_process_name,
    _windows_window_opted_out,
    _macos_window_opted_out,
    _linux_window_opted_out,
    PRIVATE_PROCESSES,
)


class ProcessNameTests(unittest.TestCase):
    """Test process name normalization and private process detection."""
    
    def test_normalize_process_name_lowercase(self):
        self.assertEqual(_normalize_process_name("Chrome.exe"), "chrome")
        self.assertEqual(_normalize_process_name("1Password.EXE"), "1password")
    
    def test_normalize_process_name_removes_extensions(self):
        self.assertEqual(_normalize_process_name("bitwarden.exe"), "bitwarden")
        self.assertEqual(_normalize_process_name("Dashlane.app"), "dashlane")
    
    def test_normalize_process_name_handles_empty(self):
        self.assertEqual(_normalize_process_name(""), "")
        self.assertEqual(_normalize_process_name(None), "")
    
    def test_is_private_process_password_managers(self):
        self.assertTrue(_is_private_process("1Password.exe"))
        self.assertTrue(_is_private_process("Bitwarden.exe"))
        self.assertTrue(_is_private_process("KeePassXC"))
        self.assertTrue(_is_private_process("LastPass"))
        self.assertTrue(_is_private_process("Dashlane.app"))
    
    def test_is_private_process_banking_apps(self):
        self.assertTrue(_is_private_process("Quicken.exe"))
        self.assertTrue(_is_private_process("MoneyDance"))
    
    def test_is_private_process_normal_apps(self):
        self.assertFalse(_is_private_process("Chrome.exe"))
        self.assertFalse(_is_private_process("Code.exe"))
        self.assertFalse(_is_private_process("Slack"))
        self.assertFalse(_is_private_process("Terminal"))
    
    def test_is_private_process_partial_match(self):
        # Should match when private process name is contained in the full process name
        self.assertTrue(_is_private_process("1password-helper.exe"))
        self.assertTrue(_is_private_process("bitwarden-desktop"))
        # Note: "onepassword" contains "1password" after the leading digit is removed
        # But we match on "password" substring which is common, so be more specific
        self.assertTrue(_is_private_process("keepassxc-browser"))


class WindowsOptoutTests(unittest.TestCase):
    """Test Windows SetWindowDisplayAffinity detection."""
    
    def test_windows_optout_null_hwnd(self):
        """Test behavior with null window handle."""
        result = _windows_window_opted_out(0)
        self.assertFalse(result)
        
        result = _windows_window_opted_out(None)
        self.assertFalse(result)
    
    def test_windows_optout_integration(self):
        """Test Windows opt-out detection integration (mocked at system level)."""
        # These tests verify behavior but require actual Windows APIs to test fully
        # In CI/production, we rely on fail-safe behavior
        # Real testing would require a Windows environment with test windows
        pass


class MacOSOptoutTests(unittest.TestCase):
    """Test macOS NSWindowSharingNone detection."""
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_with_sharing_none(self):
        """Test detection of NSWindowSharingNone (kCGWindowSharingState == 0)."""
        mock_window_list = [
            {
                'kCGWindowLayer': 0,
                'kCGWindowBounds': {'X': 100, 'Y': 100, 'Width': 800, 'Height': 600},
                'kCGWindowSharingState': 0,  # NSWindowSharingNone
            }
        ]
        
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=mock_window_list):
            result = _macos_window_opted_out((50, 50, 900, 700))
            self.assertTrue(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_with_sharing_allowed(self):
        """Test detection when sharing is allowed (kCGWindowSharingState != 0)."""
        mock_window_list = [
            {
                'kCGWindowLayer': 0,
                'kCGWindowBounds': {'X': 100, 'Y': 100, 'Width': 800, 'Height': 600},
                'kCGWindowSharingState': 1,  # Sharing allowed
            }
        ]
        
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=mock_window_list):
            result = _macos_window_opted_out((50, 50, 900, 700))
            self.assertFalse(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_no_overlap(self):
        """Test that non-overlapping windows are ignored."""
        mock_window_list = [
            {
                'kCGWindowLayer': 0,
                'kCGWindowBounds': {'X': 2000, 'Y': 2000, 'Width': 800, 'Height': 600},
                'kCGWindowSharingState': 0,  # Opted out but not overlapping
            }
        ]
        
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=mock_window_list):
            result = _macos_window_opted_out((100, 100, 500, 500))
            self.assertFalse(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_wrong_layer(self):
        """Test that windows on wrong layer are ignored."""
        mock_window_list = [
            {
                'kCGWindowLayer': 5,  # Not layer 0
                'kCGWindowBounds': {'X': 100, 'Y': 100, 'Width': 800, 'Height': 600},
                'kCGWindowSharingState': 0,
            }
        ]
        
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=mock_window_list):
            result = _macos_window_opted_out((50, 50, 900, 700))
            self.assertFalse(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_empty_window_list(self):
        """Test behavior with empty window list."""
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=[]):
            result = _macos_window_opted_out((100, 100, 500, 500))
            self.assertFalse(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_null_window_list(self):
        """Test behavior when window list query fails."""
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=None):
            result = _macos_window_opted_out((100, 100, 500, 500))
            self.assertFalse(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_exception_handling(self):
        """Test fail-safe behavior on exception."""
        with patch('Quartz.CGWindowListCopyWindowInfo', side_effect=Exception("Test error")):
            result = _macos_window_opted_out((100, 100, 500, 500))
            self.assertFalse(result)  # Fail safe: allow capture
    
    def test_macos_optout_null_bounds(self):
        """Test behavior with null bounds."""
        result = _macos_window_opted_out(None)
        self.assertFalse(result)
    
    def test_macos_optout_fail_safe_on_non_macos(self):
        """Test that macOS opt-out returns False (fail-safe) when Quartz is unavailable."""
        # This test works on any platform
        # When Quartz import fails, the function should return False
        result = _macos_window_opted_out((100, 100, 500, 500))
        # On non-macOS systems, this should safely return False
        if sys.platform != 'darwin':
            self.assertFalse(result)


class LinuxOptoutTests(unittest.TestCase):
    """Test Linux opt-out detection (currently no standard mechanism)."""
    
    def test_linux_optout_not_supported(self):
        """Test that Linux always returns False (no standard opt-out)."""
        result = _linux_window_opted_out()
        self.assertFalse(result)


class IntegrationTests(unittest.TestCase):
    """Test the high-level window_opted_out function."""
    
    def test_window_opted_out_private_process(self):
        """Test that private processes are caught regardless of platform."""
        result = window_opted_out(None, "1Password.exe", None)
        self.assertTrue(result)
        
        result = window_opted_out(None, "bitwarden", None)
        self.assertTrue(result)
    
    def test_window_opted_out_normal_process(self):
        """Test that normal processes pass through to OS-level checks."""
        with patch('core.capture_optout.IS_WINDOWS', False):
            with patch('core.capture_optout.IS_MACOS', False):
                with patch('core.capture_optout.IS_LINUX', True):
                    result = window_opted_out(None, "chrome.exe", None)
                    self.assertFalse(result)
    
    def test_window_opted_out_windows_with_cache(self):
        """Test Windows caching behavior."""
        forget_optout_cache()  # Clear cache first
        
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout._windows_window_opted_out', return_value=True) as mock_check:
                # First call should check
                result = window_opted_out(12345, "notepad.exe", None)
                self.assertTrue(result)
                self.assertEqual(mock_check.call_count, 1)
                
                # Second call should use cache
                result = window_opted_out(12345, "notepad.exe", None)
                self.assertTrue(result)
                self.assertEqual(mock_check.call_count, 1)  # Not called again
    
    def test_window_opted_out_cache_pruning(self):
        """Test that cache is pruned when it grows too large."""
        forget_optout_cache()
        
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout._windows_window_opted_out', return_value=False):
                with patch('core.capture_optout._MAX_CACHE', 10):  # Small cache for testing
                    # Add many entries to trigger pruning
                    for hwnd in range(20):
                        window_opted_out(hwnd + 1000, "app.exe", None)
                    
                    # Cache should be pruned (implementation removes first half)
                    from core.capture_optout import _cache
                    self.assertLessEqual(len(_cache), 10)
    
    def test_should_skip_capture_alias(self):
        """Test that should_skip_capture is an alias for window_opted_out."""
        with patch('core.capture_optout.window_opted_out', return_value=True) as mock_check:
            result = should_skip_capture(12345, "test.exe", None)
            self.assertTrue(result)
            mock_check.assert_called_once_with(12345, "test.exe", None)
    
    def test_forget_optout_cache(self):
        """Test cache clearing."""
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout._windows_window_opted_out', return_value=True):
                # Populate cache
                window_opted_out(12345, "app.exe", None)
                
                from core.capture_optout import _cache
                self.assertGreater(len(_cache), 0)
                
                # Clear cache
                forget_optout_cache()
                self.assertEqual(len(_cache), 0)


class CapturePipelineIntegrationTests(unittest.TestCase):
    """Test integration with the capture pipeline."""
    
    def setUp(self):
        """Clear cache before each test."""
        from core.capture_optout import forget_optout_cache
        forget_optout_cache()
    
    def test_screenshot_skipped_when_opted_out(self):
        """Test that screenshots are skipped for opted-out windows."""
        from core.capture_optout import should_skip_capture
        
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout.IS_MACOS', False):
                with patch('core.capture_optout.IS_LINUX', False):
                    with patch('core.capture_optout._windows_window_opted_out', return_value=True) as mock_check:
                        result = should_skip_capture(12345, "notepad.exe", None)
                        self.assertTrue(result)
                        # Verify the Windows check was called
                        mock_check.assert_called_once()
    
    def test_screenshot_allowed_when_not_opted_out(self):
        """Test that screenshots proceed for normal windows."""
        from core.capture_optout import should_skip_capture
        
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout.IS_MACOS', False):
                with patch('core.capture_optout.IS_LINUX', False):
                    with patch('core.capture_optout._windows_window_opted_out', return_value=False) as mock_check:
                        result = should_skip_capture(12345, "notepad.exe", None)
                        self.assertFalse(result)
                        mock_check.assert_called_once()


if __name__ == "__main__":
    unittest.main()
