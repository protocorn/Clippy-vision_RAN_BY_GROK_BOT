# Clippy Vision v2.1.0 Release Notes (DRAFT)

> **⚠️ Pre-release Draft** — This document is a working draft for v2.1.0. Not yet tagged or published.

## Overview

This is the **first release** of the Grok Bot fork of Clippy Vision. This release builds on upstream v2.0.0 with three major improvements: experimental Linux support, expanded browser privacy detection, and comprehensive CI testing.

**Version:** `v2.1.0`

**Fork Point:** Upstream Clippy Vision v2.0.0 ([commit 8271941](https://github.com/protocorn/clippy-vision/commit/8271941), October 9, 2026)

**Included Platforms:** Windows, Linux (macOS excluded — opt-in only, requires manual validation)

## 🆕 New Features

### 1. Experimental Linux Support ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10), [#14](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/14))

**Status:** ✅ **Verified in CI (Ubuntu 22.04, unit + integration tests)**, ✅ **AppImage builds in CI**, ⚠️ **Unverified on real Linux desktops**

Clippy Vision now runs on Linux with X11 screenshot capture and basic window tracking.

**What works:**
- Window metadata collection (via `xdotool`)
- Process name resolution (via `psutil`)
- Clipboard reading (`wl-paste`, `xclip`, `xsel` with fallback)
- Idle detection (`xprintidle`, `xdotool` with fallback)
- X11 screenshots (via `mss` library with focused-window crop)
- Wayland session detection with graceful degradation
- Blank/all-black frame filtering

**Known limitations:**
- **Wayland screenshot capture not yet implemented** — Wayland sessions detect the compositor and log one warning, then skip capture (no blank JPEGs stored). X11 sessions work.
- **AT-SPI accessibility text extraction not implemented** — Linux returns empty accessible text with one-time warning.
- **Browser URL detection not implemented** — Linux cannot yet read active browser URLs.
- **Private browser window detection not implemented** — Linux does not yet detect private browsing windows.
- **No installer** — First-time Linux users must install dependencies manually (see Installation below).

**Verification:**
- ✅ CI tests pass on Ubuntu 22.04 (unit tests + Xvfb integration tests)
- ✅ AppImage builds successfully in CI with smoke checks (extract + binary verification)
- ⚠️ Not tested on real hardware with real desktop environments (GNOME, KDE, etc.)
- ⚠️ Not tested on Wayland (compositor detection works, capture skipped as expected)

**Installation (Linux):**

1. Download `ClippyVision-Linux-x64-2.1.0.AppImage` from the release
2. Make it executable: `chmod +x ClippyVision-Linux-x64-2.1.0.AppImage`
3. Install required system dependencies:
   ```bash
   # For X11 capture (required)
   sudo apt install xdotool x11-utils
   
   # For idle detection (optional)
   sudo apt install xprintidle
   
   # For clipboard reading (optional, pick one)
   sudo apt install xclip
   # OR
   sudo apt install xsel
   # OR (Wayland)
   sudo apt install wl-clipboard
   ```
4. Run the AppImage: `./ClippyVision-Linux-x64-2.1.0.AppImage`

### 2. Firefox, Opera, and Vivaldi Private Window Detection ([#8](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/8))

**Status:** ✅ **Verified in CI (unit tests)**, ⚠️ **Unverified on real Firefox/Opera/Vivaldi private windows**

Expands privacy redaction to cover Firefox, Opera, and Vivaldi in addition to the existing Chrome, Edge, and Brave support.

**Detection methods:**
- **Firefox (Windows):** Pattern-based detection of "Private Browsing" markers in window/child element names
- **Firefox (macOS):** AppleScript mode detection (`mode = "private"`)
- **Opera and Vivaldi (Windows):** Chromium-based BrowserRootView parenthetical pattern detection
- **Opera (macOS):** AppleScript mode detection (hypothesis, not confirmed)

**Coverage:**

| Browser | Windows | macOS | Linux | Verification |
|---------|---------|-------|-------|--------------|
| Chrome | ✅ | ✅ | ❌ | ✅ Inherited from upstream |
| Edge | ✅ | ✅ | ❌ | ✅ Inherited from upstream |
| Brave | ✅ | ✅ | ❌ | ✅ Inherited from upstream |
| **Firefox** | ✅ | ✅ | ❌ | ⚠️ **Unit tests only** |
| **Opera** | ✅ | ⚠️ | ❌ | ⚠️ **Unit tests only** |
| **Vivaldi** | ✅ | ❌ | ❌ | ⚠️ **Unit tests only** |
| Safari | ❌ | ❌ | — | Not implemented |

**Verification:**
- ✅ All 36 unit tests pass (mocked accessibility tree structures)
- ⚠️ Not tested on actual Firefox/Opera/Vivaldi private windows with real UI Automation APIs
- ⚠️ macOS AppleScript detection not tested on real Opera/Vivaldi

### 3. CI Testing on Ubuntu and Windows ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))

**Status:** ✅ **Verified (CI runs on every PR)**

Automated pytest testing on both Ubuntu and Windows, with platform-specific test isolation.

**What's tested:**
- Core modules import without crashing
- Platform-specific capture and accessibility functions
- Privacy window detection logic
- Memory consolidation and timeline grouping
- SQL generation and OCR cropping

**Test markers:**
- `@pytest.mark.linux` — Linux-specific tests (run on Ubuntu)
- `@pytest.mark.windows` — Windows UI Automation tests (run on Windows)
- `@pytest.mark.macos` — macOS AX/AppleScript tests (skipped in CI)
- `@pytest.mark.requires_gui` — GUI tests (skipped in CI)
- `@pytest.mark.requires_ollama` — Ollama server tests (skipped in CI)
- `@pytest.mark.integration` — Full integration tests (skipped in CI)

**Verification:**
- ✅ CI runs on every push to main and every pull request
- ✅ Tests pass on Ubuntu 22.04 and Windows Server 2022

### 4. MCP Setup Guides ([#9](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/9))

**Status:** ✅ **Verified (documentation)**

Added comprehensive setup guides for integrating Clippy Vision with MCP clients:
- Claude Desktop configuration guide (`docs/mcp-clients/claude-desktop.md`)
- LM Studio integration instructions (referenced in main MCP docs)

### 5. Project Templates ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))

**Status:** ✅ **Verified (GitHub templates active)**

- Bug report template (`.github/ISSUE_TEMPLATE/bug_report.md`)
- Feature request template (`.github/ISSUE_TEMPLATE/feature_request.md`)
- Pull request template (`.github/PULL_REQUEST_TEMPLATE.md`)

## 🐛 Bug Fixes

- Fixed Linux metadata collection to resolve PIDs to process names instead of storing raw PIDs ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))
- Fixed CI to properly exclude platform-specific tests using pytest markers ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))

## 🔧 Changes

- Updated roadmap to focus on free, high-impact features ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
- Deferred signed installers to future milestone (requires ~$400-600/year budget) ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
- Made Windows/macOS imports lazy-loaded for cross-platform compatibility ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))

## ⚠️ Known Limitations

### Unsigned Installers

**All installers (Windows, macOS, Linux) are UNSIGNED.**

**Windows:**
- Windows SmartScreen will show "Windows protected your PC" warning
- Click "More info" → "Run anyway" to install
- This is expected behavior for unsigned installers
- **Mitigation:** See installation instructions with screenshots in the README

**macOS:**
- macOS Gatekeeper will block the installer
- Right-click the `.dmg` → "Open" → "Open" to bypass
- OR: `xattr -d com.apple.quarantine ClippyVision-macOS-*.dmg`
- This is expected behavior for unsigned installers from unidentified developers

**Linux:**
- AppImage requires `chmod +x` before first run
- This is standard for AppImage files
- No code signing available for Linux AppImages

**Why unsigned?**
- Code signing costs ~$400-600/year (Windows EV certificate + Apple Developer Program)
- This fork has zero budget and prioritizes free, high-impact features
- Signed installers deferred to future milestone

### Linux Limitations

See "Known limitations" in the Linux Support section above.

### Browser Coverage

- Safari private browsing not detected (macOS)
- All browser private window detection not implemented on Linux

## 📦 Release Assets

This release includes **two** installer packages (macOS excluded):

1. **`ClippyVision-Windows-Setup-2.1.0.exe`** (unsigned)
   - Windows 10/11 x64
   - NSIS installer with start menu shortcuts
   - Includes Python dependencies bundled
   - ✅ Builds successfully in CI with smoke checks

2. **`ClippyVision-Linux-x64-2.1.0.AppImage`** (unsigned)
   - Linux x64 (Ubuntu 22.04+, other distros with X11)
   - Requires `chmod +x` and system dependencies (see Installation above)
   - Experimental support, not tested on real hardware
   - ✅ Builds successfully in CI with smoke checks (extract + binary verification)

**macOS installers are NOT included in this release:**
- macOS builds are opt-in only (manual workflow_dispatch trigger required)
- Require validation on Apple Silicon and Intel before upload
- See upstream release for signed macOS builds

## 🔗 Links

- **Changelog:** [CHANGELOG.md](../CHANGELOG.md)
- **Installation:** [README.md](../../README.md)
- **Usage Guide:** [docs/usage.md](../usage.md)
- **Architecture:** [docs/architecture.md](../architecture.md)
- **MCP Setup:** [docs/mcp.md](../mcp.md)
- **Contributing:** [CONTRIBUTING.md](../../CONTRIBUTING.md)

## 📝 Release Checklist (for maintainer)

Before tagging `v2.1.0`:

- [x] All PRs merged to main
- [x] CI passes on main
- [x] CHANGELOG.md updated with version and date
- [x] Release notes finalized in docs/release-notes/vNEXT.md
- [x] Version confirmed as v2.1.0
- [x] macOS excluded from this release (opt-in only)
- [x] CI builds Windows + Linux installers successfully with smoke checks
- [ ] This file renamed from `vNEXT.md` to `v2.1.0.md`
- [ ] Version bumped in `electron-ui/package.json` to 2.1.0
- [ ] CHANGELOG.md release date updated
- [ ] Tag pushed: `git tag v2.1.0 && git push origin v2.1.0`
- [ ] Draft release created by workflow with Windows and Linux installers attached
- [ ] Release notes copied from this file to GitHub release description
- [ ] Draft release reviewed and published

## 🙏 Credits

This release was prepared by Grok Bot (an AI assistant) as part of an open-source experiment. All credit for the original Clippy Vision design and implementation goes to [protocorn](https://github.com/protocorn) (Sahil Chordia) and the upstream contributors.

- **Upstream Clippy Vision:** [github.com/protocorn/clippy-vision](https://github.com/protocorn/clippy-vision)
- **License:** AGPL-3.0-only (inherited from upstream)
