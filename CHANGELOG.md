# Changelog

All notable changes to this project (the Grok Bot fork of Clippy Vision) will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.1.0] - Unreleased

First release of the Grok Bot fork. Adds experimental Linux support, expands browser privacy detection, and establishes CI testing infrastructure.

**Note:** macOS installers are not included in this release (opt-in only, requires manual validation).

### Added
- Linux platform support with X11 screenshot capture ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10), [#14](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/14))
  - Window metadata collection via `xdotool`
  - Process name resolution via `psutil`
  - Clipboard reading (`wl-paste`, `xclip`, `xsel`)
  - Idle detection (`xprintidle`, `xdotool`)
  - X11 screenshots via `mss` library with focused-window crop
  - Wayland session detection with graceful degradation
  - Blank/all-black frame guard for screenshot quality
- Firefox, Opera, and Vivaldi private window detection on Windows ([#8](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/8))
  - Firefox: pattern-based detection of "Private Browsing" markers
  - Opera and Vivaldi: Chromium-based BrowserRootView detection
  - macOS support via AppleScript mode detection
- CI testing on Ubuntu and Windows ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
  - Automated pytest runs on both platforms
  - Platform-specific test markers for proper test isolation
- MCP setup guides ([#9](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/9))
  - Claude Desktop configuration guide
  - LM Studio integration instructions
- Issue and pull request templates ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
  - Bug report template with environment details
  - Feature request template with structured format
  - Pull request template with comprehensive checklist

### Changed
- Updated project roadmap to focus on free, high-impact features ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
- Deferred signed installers (requires ~$400-600/year budget) ([#7](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/7))
- Lazy-loaded Windows/macOS imports for cross-platform compatibility ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))

### Fixed
- Linux metadata collection now resolves PIDs to process names ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))
- CI workflow properly excludes platform-specific tests ([#10](https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/10))

## [2.0.0] - 2024-10-09

This is the fork point. All changes above are additions made by the Grok Bot fork after upstream Clippy Vision v2.0.0 (commit [8271941](https://github.com/protocorn/clippy-vision/commit/8271941)).

For changes prior to the fork, see the [upstream Clippy Vision repository](https://github.com/protocorn/clippy-vision).

[2.1.0]: https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/compare/8271941...HEAD
[2.0.0]: https://github.com/protocorn/clippy-vision/releases/tag/v2.0.0
