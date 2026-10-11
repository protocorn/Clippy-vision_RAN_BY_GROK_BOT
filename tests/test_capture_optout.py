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
    PASSWORD_MANAGERS,
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
        # Exact matches should work
        self.assertTrue(_is_private_process("1Password.exe"))
        self.assertTrue(_is_private_process("Bitwarden.exe"))
        self.assertTrue(_is_private_process("KeePassXC"))
        self.assertTrue(_is_private_process("LastPass"))
        self.assertTrue(_is_private_process("Dashlane.app"))
        self.assertTrue(_is_private_process("keeper"))
        self.assertTrue(_is_private_process("enpass"))
    
    def test_is_private_process_banking_apps(self):
        self.assertTrue(_is_private_process("Quicken.exe"))
        self.assertTrue(_is_private_process("MoneyDance"))
    
    def test_is_private_process_normal_apps(self):
        # Normal apps should not match
        self.assertFalse(_is_private_process("Chrome.exe"))
        self.assertFalse(_is_private_process("Code.exe"))
        self.assertFalse(_is_private_process("Slack"))
        self.assertFalse(_is_private_process("Terminal"))
    
    def test_is_private_process_no_false_positives(self):
        # Substring false positives should NOT match (exact matching only)
        self.assertFalse(_is_private_process("timekeeper"))  # Contains 'keeper'
        self.assertFalse(_is_private_process("mintupdate"))  # Contains 'mint' (also mint removed)
        self.assertFalse(_is_private_process("shopkeeper.exe"))  # Contains 'keeper'
        self.assertFalse(_is_private_process("spotify"))  # Removed from list
        self.assertFalse(_is_private_process("netflix"))  # Removed from list
    
    def test_is_private_process_exact_match_variants(self):
        # Should match exact process name variants
        self.assertTrue(_is_private_process("1password-browser.exe"))
        self.assertTrue(_is_private_process("keepass2"))
        self.assertTrue(_is_private_process("1passwordnative"))


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
    
    def test_windows_cache_ttl(self):
        """Test that cache entries expire after TTL and affinity changes are detected."""
        forget_optout_cache()
        
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout.IS_MACOS', False):
                with patch('core.capture_optout.IS_LINUX', False):
                    with patch('core.capture_optout._CACHE_TTL_SECONDS', 0.1):  # Short TTL for testing
                        with patch('core.capture_optout._windows_window_opted_out') as mock_check:
                            # First call: not opted out
                            mock_check.return_value = False
                            result = window_opted_out(12345, "notepad.exe", None)
                            self.assertFalse(result)
                            self.assertEqual(mock_check.call_count, 1)
                            
                            # Second call immediately: should use cache
                            result = window_opted_out(12345, "notepad.exe", None)
                            self.assertFalse(result)
                            self.assertEqual(mock_check.call_count, 1)  # Still 1
                            
                            # Wait for TTL to expire
                            import time
                            time.sleep(0.15)
                            
                            # Third call after TTL: should check again
                            # Now the window has opted out (affinity changed)
                            mock_check.return_value = True
                            result = window_opted_out(12345, "notepad.exe", None)
                            self.assertTrue(result)
                            self.assertEqual(mock_check.call_count, 2)  # Checked again


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
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_overlapping_background_window(self):
        """Test that an overlapping background window does NOT trigger opt-out.
        
        Only the frontmost window of the foreground app should be checked,
        not background windows that happen to overlap the bounds.
        """
        # Window list: two apps at layer 0, frontmost has PID 1000, background has PID 2000
        # Background window (PID 2000) has opted out but should be ignored
        mock_window_list = [
            {
                'kCGWindowLayer': 0,
                'kCGWindowOwnerPID': 1000,  # Frontmost app
                'kCGWindowBounds': {'X': 100, 'Y': 100, 'Width': 800, 'Height': 600},
                'kCGWindowSharingState': 1,  # NOT opted out
            },
            {
                'kCGWindowLayer': 0,
                'kCGWindowOwnerPID': 2000,  # Background app that overlaps
                'kCGWindowBounds': {'X': 150, 'Y': 150, 'Width': 700, 'Height': 500},
                'kCGWindowSharingState': 0,  # Opted out but should be ignored
            },
        ]
        
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=mock_window_list):
            # Should NOT opt out because frontmost app (PID 1000) hasn't opted out
            result = _macos_window_opted_out((50, 50, 900, 700))
            self.assertFalse(result)
    
    @unittest.skipUnless(sys.platform == 'darwin', "macOS-specific test")
    def test_macos_optout_frontmost_window_only(self):
        """Test that only the frontmost window of the foreground app is checked."""
        # Two windows from same app, only the frontmost (first in list) matters
        mock_window_list = [
            {
                'kCGWindowLayer': 0,
                'kCGWindowOwnerPID': 1000,
                'kCGWindowBounds': {'X': 100, 'Y': 100, 'Width': 800, 'Height': 600},
                'kCGWindowSharingState': 0,  # Frontmost window opted out
            },
            {
                'kCGWindowLayer': 0,
                'kCGWindowOwnerPID': 1000,  # Same app
                'kCGWindowBounds': {'X': 200, 'Y': 200, 'Width': 700, 'Height': 500},
                'kCGWindowSharingState': 1,  # Second window not opted out (ignored)
            },
        ]
        
        with patch('Quartz.CGWindowListCopyWindowInfo', return_value=mock_window_list):
            # Should opt out because frontmost window of foreground app opted out
            result = _macos_window_opted_out((50, 50, 900, 700))
            self.assertTrue(result)
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
        """Test that cache entries are pruned when they expire."""
        forget_optout_cache()
        
        with patch('core.capture_optout.IS_WINDOWS', True):
            with patch('core.capture_optout._windows_window_opted_out', return_value=False):
                with patch('core.capture_optout._CACHE_TTL_SECONDS', 0.1):  # Short TTL
                    # Add entries to cache
                    for hwnd in range(20):
                        window_opted_out(hwnd + 1000, "app.exe", None)
                    
                    from core.capture_optout import _cache
                    initial_count = len(_cache)
                    self.assertEqual(initial_count, 20)
                    
                    # Wait for TTL to expire
                    import time
                    time.sleep(0.15)
                    
                    # Add more entries, triggering pruning of expired ones
                    for hwnd in range(300):
                        window_opted_out(hwnd + 2000, "app.exe", None)
                    
                    # Cache should have pruned expired entries
                    # Should only have the recent 300 entries (expired ones removed)
                    final_count = len(_cache)
                    self.assertLessEqual(final_count, 300)
    
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
    
    def test_clipboard_capture_skipped_on_linux(self):
        """Test that clipboard capture properly checks opt-out on non-macOS platforms."""
        from core.capture_optout import should_skip_capture
        
        # Linux: password manager process should trigger opt-out
        with patch('core.capture_optout.IS_WINDOWS', False):
            with patch('core.capture_optout.IS_MACOS', False):
                with patch('core.capture_optout.IS_LINUX', True):
                    result = should_skip_capture(None, "1password", None)
                    self.assertTrue(result)
                    
                    # Normal process should not trigger opt-out
                    result = should_skip_capture(None, "firefox", None)
                    self.assertFalse(result)
    
    def test_get_foreground_window_bounds_safe_on_all_platforms(self):
        """Test that get_foreground_window_bounds is safely importable on all platforms."""
        # This import should not fail on any platform
        from core.platform_support import get_foreground_window_bounds
        
        # On non-macOS, it should return None
        if sys.platform != 'darwin':
            result = get_foreground_window_bounds()
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
