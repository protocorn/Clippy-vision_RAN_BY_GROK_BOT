# Changelog

All notable changes to this project (the Grok Bot fork of Clippy Vision) will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.1.0] - Unreleased

First release of the Grok Bot fork. Adds experimental Linux support, in-app chat, expands browser privacy detection, and establishes CI plus unsigned installer dry-runs.

**Note:** macOS installers are not included in this release (opt-in only, requires manual validation).

Verification labels used below:
- **CI-only** — unit/integration tests in GitHub Actions
- **Xvfb launch** — packaged Linux AppImage launched under Xvfb in the release dry-run
- **Windows silent install** — packaged NSIS installer silent-installed on `windows-latest` in the release dry-run
- **real machine** — a physical desktop; nobody has done that for this fork's v2.1.0 work

### Added
- Linux platform support with X11 screenshot capture ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10), [#14](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/14)) — **CI-only** (pytest, including Xvfb screenshot tests)
  - Window metadata collection via `xdotool`
  - Process name resolution via `psutil`
  - Clipboard reading (`wl-paste`, `xclip`, `xsel`)
  - Idle detection (`xprintidle`, `xdotool`)
  - X11 screenshots via `mss` with focused-window crop
  - Wayland session detection with graceful degradation
  - Blank/all-black frame guard for screenshot quality
- Linux AT-SPI accessibility text extraction ([#20](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/20)) — **CI-only**
- Firefox, Opera, and Vivaldi private window detection on Windows ([#8](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/8)) — **CI-only**
  - Firefox: pattern-based detection of "Private Browsing" markers
  - Opera and Vivaldi: Chromium-based BrowserRootView detection
  - macOS support via AppleScript mode detection (unit tests; Opera marked hypothesis)
- In-app chat backend (`/chat`, `/chat/stream`) with activity context retrieval ([#23](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/23)) — **CI-only**
- In-app chat UI with streaming ([#25](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/25)) — **CI-only**; not exercised against a real Ollama model
- Live progress while the setup wizard downloads Ollama models ([#19](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/19)) — **CI-only** (parser tests; wizard UI itself is not driven in CI)
- Captured screen text marked untrusted in MCP replies and in-app chat ([#27](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/27)) — **CI-only**
- Honor OS-level window capture opt-outs ([#28](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/28)) — **CI-only** (mocked Win32 `GetWindowDisplayAffinity`, macOS window-sharing state, Linux no-op plus process-name fallback). **Not real machine.** Linux has no per-window OS capture API.
- VS Code MCP setup guide ([#29](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/29), [@Afrin-banu-A](https://github.com/Afrin-banu-A)) — documentation; the author marked the setup steps as not verified on a real VS Code install
- CI testing on Ubuntu and Windows ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7)) — **CI-only**
- Unsigned Windows NSIS installer and Linux AppImage release workflow with PR dry-run ([#15](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/15), this PR) — **Xvfb launch** and **Windows silent install**: packaged app spawned the backend and `GET /health` returned 200 `{"status":"ok"}` ([run 38286025883](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/actions/runs/38286025883) on `d068c49`, which includes #28/#29/#32). Setup was pre-seeded and Ollama stubbed; not a real-machine test.
- MCP setup guides ([#9](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/9), [#13](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/13), [#29](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/29))
- Issue and pull request templates ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))

### Changed
- Updated project roadmap to focus on free, high-impact features ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
- Deferred signed installers (requires ~$400-600/year budget) ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
- Lazy-loaded Windows/macOS imports for cross-platform compatibility ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))

### Fixed
- Linux metadata collection now resolves PIDs to process names ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10)) — **CI-only**
- CI workflow properly excludes platform-specific tests ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))
- Setup wizard now accepts Linux and allows users to proceed ([#26](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/26)) — **CI-only**
  - Previously showed "Blocked" / "Cannot continue" for all Linux users
  - Now passes OS check and displays "Ubuntu 22.04+ (experimental)"
  - Linux with integrated GPU uses system RAM for VRAM grading
- Flaky X11 screenshot test under Xvfb waits for the window to map and polls for a non-blank frame ([#24](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/24)) — **CI-only**
- VS Code one-click Connect wrote `mcp.json` to a Windows-style path on macOS and Linux ([#30](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/issues/30), [#32](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/32)) — **CI-only** (`node --test` path tests on ubuntu-latest and windows-latest). Paths: Windows `%APPDATA%\Code\User\mcp.json`, macOS `~/Library/Application Support/Code/User/mcp.json`, Linux `$XDG_CONFIG_HOME/Code/User/mcp.json` or `~/.config/Code/User/mcp.json`. **Not real machine** (Connect was not clicked in VS Code).

### Known Issues
- Private-browsing docs overstate coverage ([#16](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/issues/16)): `docs/usage.md` says Firefox, Opera, and Vivaldi "are covered on Windows" (those detectors are **CI-only**, not a real private window) and then contradicts itself with "Firefox, Opera, and Safari are not covered." `PROJECT_VISION.md` says all six browsers "are blacked out on Windows" as if that were verified. Linux has no private-window detection. Shipped without waiting for #16.
- Python **3.11+** is required and is **not bundled**. The packaged app spawns `CLIPPY_PYTHON` if set, otherwise `python3` (Linux/macOS) or `python` (Windows) from PATH. `requirements.txt` does not pin a Python version. CI uses Python 3.12. See README.md for wizard behavior when Python is missing.
- Backend spawn is gated on `setup_complete.json` (first-run wizard). The release dry-run pre-seeds that file and stubs Ollama. With that bypass, `GET /health` returned 200 `{"status":"ok"}` on Linux (Xvfb AppImage, port 39367) and Windows (silent NSIS install, port 61677) in [run 38286025883](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/actions/runs/38286025883). That does not cover the wizard, Ollama, a real model, or a real desktop.
- Unsigned installers trigger SmartScreen/Gatekeeper warnings on first install.
- No **real machine** testing of capture, chat, or setup for this fork.

## [2.0.0] - 2024-10-09

This is the fork point. All changes above are additions made by the Grok Bot fork after upstream Clippy Vision v2.0.0 (commit [8271941](https://github.com/protocorn/clippy-vision/commit/8271941)).

For changes prior to the fork, see the [upstream Clippy Vision repository](https://github.com/protocorn/clippy-vision).

[2.1.0]: https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/compare/8271941...HEAD
[2.0.0]: https://github.com/protocorn/clippy-vision/releases/tag/v2.0.0
