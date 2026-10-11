"""Detect windows that request not to be captured via OS-level signals.

This module checks for OS-provided opt-out mechanisms:
- Windows: SetWindowDisplayAffinity WDA_EXCLUDEFROMCAPTURE or WDA_MONITOR
- macOS: NSWindowSharingNone (kCGWindowSharingState == 0)
- Linux: Currently no standardized mechanism (documented)

Password managers, DRM apps, and banking software often use these APIs.
When detected, skip screenshot, OCR, accessibility text, and clipboard
capture for that moment and record a minimal redacted event.
"""

from __future__ import annotations

import sys
import threading
from typing import Optional

try:
    from core.platform_support import IS_MACOS, IS_WINDOWS, IS_LINUX
except ImportError:
    from platform_support import IS_MACOS, IS_WINDOWS, IS_LINUX

# Cache window opt-out status to avoid repeated OS queries
_cache_lock = threading.Lock()
_cache: dict[int, bool] = {}
_MAX_CACHE = 256

# Well-known password manager and private-mode processes that commonly opt out
# These are checked as a fallback when OS-level detection isn't available
PRIVATE_PROCESSES = {
    # Password managers
    "1password",
    "bitwarden",
    "dashlane",
    "keepass",
    "keepassxc",
    "lastpass",
    "keeper",
    "enpass",
    "nordpass",
    "roboform",
    # Banking/financial
    "moneydance",
    "quicken",
    "mint",
    # DRM/media
    "spotify",
    "netflix",
}


def _normalize_process_name(process_name: str) -> str:
    """Normalize process name for comparison (lowercase, no extension)."""
    name = (process_name or "").lower().strip()
    # Remove common extensions
    for ext in [".exe", ".app"]:
        if name.endswith(ext):
            name = name[:-len(ext)]
    return name


def _is_private_process(process_name: str) -> bool:
    """Check if process is a known private/sensitive application."""
    normalized = _normalize_process_name(process_name)
    return any(private in normalized for private in PRIVATE_PROCESSES)


def _windows_window_opted_out(hwnd: int) -> bool:
    """Check if a Windows window has opted out via SetWindowDisplayAffinity.
    
    Windows apps can call SetWindowDisplayAffinity with:
    - WDA_EXCLUDEFROMCAPTURE (0x11): Exclude from all capture
    - WDA_MONITOR (0x01): Only show on physical display (blocks remote/capture)
    
    Returns True if the window has requested capture blocking.
    Fails safe: returns False on error (allows capture).
    """
    if not hwnd:
        return False
    
    try:
        import ctypes
        from ctypes import wintypes
        
        # GetWindowDisplayAffinity constants
        WDA_NONE = 0x00
        WDA_MONITOR = 0x01
        WDA_EXCLUDEFROMCAPTURE = 0x11
        
        # GetWindowDisplayAffinity retrieves the current affinity setting
        user32 = ctypes.windll.user32
        affinity = wintypes.DWORD()
        
        result = user32.GetWindowDisplayAffinity(
            wintypes.HWND(hwnd),
            ctypes.byref(affinity)
        )
        
        if not result:
            # API call failed - fail safe (allow capture)
            return False
        
        # Check if any opt-out flag is set
        return affinity.value in (WDA_MONITOR, WDA_EXCLUDEFROMCAPTURE)
        
    except Exception as e:
        # Fail safe: log but allow capture
        print(f"[capture_optout] Windows affinity check error: {e}", file=sys.stderr)
        return False


def _macos_window_opted_out(bounds: tuple[int, int, int, int] | None) -> bool:
    """Check if a macOS window has opted out via NSWindowSharingNone.
    
    macOS apps can set sharingType to NSWindowSharingNone to prevent capture.
    CGWindowListCopyWindowInfo exposes this as kCGWindowSharingState == 0.
    
    Returns True if the frontmost window has NSWindowSharingNone.
    Fails safe: returns False on error (allows capture).
    """
    if not bounds:
        return False
    
    try:
        # Use Quartz to query window sharing state
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )
        
        # Get all on-screen windows
        window_list = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID
        )
        
        if not window_list:
            return False
        
        # Check the frontmost window(s) that overlap our bounds
        for window in window_list:
            # kCGWindowLayer 0 is typically the frontmost app layer
            layer = window.get("kCGWindowLayer", -1)
            if layer != 0:
                continue
            
            # Check if this window overlaps the foreground bounds
            window_bounds = window.get("kCGWindowBounds")
            if not window_bounds:
                continue
            
            wx = int(window_bounds.get("X", 0))
            wy = int(window_bounds.get("Y", 0))
            ww = int(window_bounds.get("Width", 0))
            wh = int(window_bounds.get("Height", 0))
            
            # Simple overlap check with foreground window
            if not (wx < bounds[2] and wx + ww > bounds[0] and 
                   wy < bounds[3] and wy + wh > bounds[1]):
                continue
            
            # kCGWindowSharingState: 0 = NSWindowSharingNone (opted out)
            sharing_state = window.get("kCGWindowSharingState", 1)
            if sharing_state == 0:
                return True
        
        return False
        
    except Exception as e:
        # Fail safe: log but allow capture
        print(f"[capture_optout] macOS sharing state check error: {e}", file=sys.stderr)
        return False


def _linux_window_opted_out() -> bool:
    """Check if a Linux window has opted out of capture.
    
    Linux/X11 and Wayland do not have a standardized opt-out mechanism
    comparable to Windows' SetWindowDisplayAffinity or macOS's NSWindowSharingNone.
    
    Some possibilities that don't exist as standard:
    - No X11 window property for "do not capture"
    - Wayland portals have screen-sharing consent, but no per-window opt-out
    - PipeWire can respect app flags, but these aren't standardized
    
    For now, return False (no detection available).
    Applications can use process-name checking via PRIVATE_PROCESSES instead.
    """
    return False


def window_opted_out(hwnd: int | None = None, process_name: str = "", 
                     bounds: tuple[int, int, int, int] | None = None) -> bool:
    """Check if the foreground window has opted out of screen capture.
    
    Checks OS-level signals:
    - Windows: GetWindowDisplayAffinity for WDA_EXCLUDEFROMCAPTURE or WDA_MONITOR
    - macOS: CGWindowList kCGWindowSharingState for NSWindowSharingNone
    - Linux: No standard mechanism (returns False unless process-name match)
    
    Also checks against PRIVATE_PROCESSES for well-known password managers
    and sensitive apps as a fallback.
    
    Args:
        hwnd: Windows window handle (Windows only)
        process_name: Process name for fallback process-based checking
        bounds: Window bounds for macOS sharing state lookup
    
    Returns:
        True if the window has opted out and should not be captured.
        False otherwise (including on error - fail safe).
    """
    # Check process-name fallback first (fastest, works on all platforms)
    if process_name and _is_private_process(process_name):
        return True
    
    # Platform-specific OS-level checks
    if IS_WINDOWS and hwnd:
        # Check cache first
        with _cache_lock:
            cached = _cache.get(hwnd)
            if cached is not None:
                return cached
        
        opted_out = _windows_window_opted_out(hwnd)
        
        # Cache the result
        with _cache_lock:
            _cache[hwnd] = opted_out
            # Prune cache if it gets too large
            if len(_cache) > _MAX_CACHE:
                # Remove oldest entries (first half)
                for key in list(_cache.keys())[:_MAX_CACHE // 2]:
                    _cache.pop(key, None)
        
        return opted_out
    
    elif IS_MACOS and bounds:
        # macOS: check sharing state (not cached - relatively fast)
        return _macos_window_opted_out(bounds)
    
    elif IS_LINUX:
        # Linux: no standard opt-out mechanism
        return _linux_window_opted_out()
    
    # Default: allow capture
    return False


def forget_optout_cache() -> None:
    """Clear the opt-out status cache.
    
    Call this when windows may have changed their affinity settings,
    or periodically to prevent unbounded cache growth.
    """
    with _cache_lock:
        _cache.clear()


def should_skip_capture(hwnd: int | None = None, process_name: str = "",
                       bounds: tuple[int, int, int, int] | None = None) -> bool:
    """High-level check: should we skip capture for this window?
    
    Alias for window_opted_out with clearer naming for capture pipeline.
    """
    return window_opted_out(hwnd, process_name, bounds)
