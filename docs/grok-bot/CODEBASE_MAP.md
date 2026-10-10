# Clippy Vision Codebase Map

**Generated:** 2026-10-10  
**Base:** v2.0.0 (commit 8271941)  
**Purpose:** Architectural overview and entry points for contributors and maintainers

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [Key Directories](#key-directories)
4. [Core Modules](#core-modules)
5. [Entry Points](#entry-points)
6. [Storage & Schema](#storage--schema)
7. [Platform Support](#platform-support)
8. [Testing](#testing)
9. [Building & Packaging](#building--packaging)
10. [Known Gaps & Tech Debt](#known-gaps--tech-debt)

---

## Overview

Clippy Vision is a local-first desktop application that captures screen activity, stores it in a searchable local database, and exposes memory retrieval through MCP (Model Context Protocol) tools. The app consists of:

- **Electron desktop UI** (`electron-ui/`) - tray app, timeline viewer, settings
- **Python backend** (`core/`, `agent/`, `api_server.py`) - capture, summarization, memory, MCP server
- **Local LLM runtime** - Ollama for classification, summaries, and memory distillation
- **SQLite database** - all events, sessions, memory, and metadata

**No vision model on the capture path.** Screen text comes from accessibility APIs (Windows UI Automation, macOS AX APIs) with RapidOCR fallback. Classification and summarization use the user-chosen chat model (e.g., `qwen3:8b`).

---

## Architecture & Data Flow

### 1. Capture Pipeline

**Entry:** `core/screen_capture.py` (separate Python process)

1. **Activity detection** - keyboard listener (pynput), clipboard monitor, foreground window polling
2. **Screenshot scheduling** - `core/screenshot_scheduler.py` triggers screenshots on activity bursts
3. **Accessibility text extraction** - `core/accessibility_text.py` walks UI trees on background worker (`core/uia_worker.py`)
4. **Classification** - three-tier pipeline:
   - **Tier 0:** Rule-based (deterministic, instant) - keystroke count, known background processes
   - **Tier 1:** Feature-based scoring - typing deviation from baseline, context novelty, clipboard length
   - **Tier 2:** LLM fallback - sends last 3 events + current to chat model for context-aware verdict
5. **Storage** - events stored in SQLite via `core/storage.py`

**Platform-specific:**
- Windows: `pywin32` + `uiautomation` for accessibility, `mss` for screenshots
- macOS: `pyobjc` frameworks (Quartz, Cocoa, ApplicationServices) for both

**Privacy layer:** `core/privacy_settings.py`, `core/secret_patterns.py`, `core/private_windows.py`
- Password fields painted out of screenshots before storage
- Private browsing windows (Chrome, Edge, Brave) blacked out
- Secret-shaped text (API keys, tokens) stripped from OCR/accessibility text

### 2. Enrichment & Summarization

**Entry:** `core/background_jobs.py` starts background workers when API server launches

**Screenshot processing** (`core/screenshot_processor.py`):
- Perceptual hashing (imagehash) to group visually identical screenshots
- RapidOCR runs only when accessibility text is empty or too thin
- Text stored with nearest event or creates new `screenshot_analysis` event

**Summarization** (`core/summarizer.py`):
- Wakes every 60 seconds
- Groups unsummarized events into windows (10-min gap, 30-min max duration)
- Sends to chat model with structured JSON schema
- Stores session summaries in `sessions` table
- Embeds summary text with `all-MiniLM-L6-v2` for semantic search

**Deferred accessibility text:**
- Slow UI walks write text after capture timeout
- Longer reads replace shorter ones for the same frame
- Sessions with delayed text re-summarized (`get_sessions_needing_refresh`)

### 3. Memory Consolidation (Distillation)

**Entry:** `core/distil.py`, `core/memory_consolidation.py`

**Runs:** Every 5 sessions (triggered by summarizer)

**Pipeline:**
1. Extract behavioral facts from recent summaries
2. Embed each fact with `all-MiniLM-L6-v2`
3. Compare against existing cluster centroids (cosine similarity, threshold 0.75)
4. Route to closest cluster or create new one
5. Second LLM call: **ADD / UPDATE / NOOP / CONFLICT**
6. Store in `memory_facts` (durable claims) or `memory_candidates` (single-day observations)

**Conflict resolution:**
- Contradicting facts stored in `memory_conflicts`
- User corrections via Settings or MCP `save_identity` close conflicts

**Freshness:**
- `core/memory_freshness.py` tracks when patterns were last confirmed
- Candidates require repetition on a different day to become facts

### 4. API Server & Timeline

**Entry:** `api_server.py` (FastAPI / Uvicorn)

**Endpoints:**
- `/sessions`, `/timeline/sessions` - session list and search
- `/screenshots` - search screenshots by text
- `/user/profile`, `/settings/*` - user identity, privacy, capture settings
- `/conversations` - archived in-app chat history (read-only, no new writes)

**Background tasks (on startup):**
- Intro rebuild daemon (`core/intro_builder.py`) - weekly refresh of user intro
- Background jobs (`core/background_jobs.py`) - summarizer, OCR backlog, distil
- Event RAG indexer (`core/rag.py`) - opt-in, default off
- Performance monitor (`core/performance_metrics.py`)

### 5. MCP Server

**Entry:** `mcp_server.py` (FastMCP)

**Tools exposed:**
- `search_sessions_tool` - broad time windows, daily/weekly overviews
- `search_events_tool` - specific messages, OCR text, exact URLs, clipboard
- `search_bounded_tool` - keyword search with explicit time bounds and pagination
- `list_sessions_tool` - chronological deduped session list
- `activity_coverage_tool` - hourly event-count buckets (detects capture gaps)
- `list_screenshots_tool`, `get_screenshot_tool` - screenshot access
- `recall_memory_tool` - semantic search over memory facts
- `remember_turn_tool` - save agent conversation turns as memory candidates
- `save_identity_tool`, `save_note_tool` - user-provided identity and notes
- `find_files_tool`, `list_workspace_roots_tool` - filesystem search

**Privacy scrubbing:**
- Every tool reply passes through `core/cloud_egress.py`
- Secrets, private windows, and de-contextualized facts withheld before reply
- If filter fails, returns `"Cloud result withheld. The privacy filter did not finish."`

**Client setup:**
- Settings → Connect apps generates per-client JSON config
- Supports Cursor, Claude Desktop, VS Code, Devin, Cline, Roo Code, JetBrains, etc.

---

## Key Directories

```
.
├── agent/              # MCP tools and retrieval logic
│   ├── mcp_server.py   # (root) MCP entry point
│   ├── mcp_query.py    # Tool implementations (search, list, coverage)
│   ├── retrieval.py    # search_sessions, search_events
│   ├── memory.py       # recall_memory, save_identity, remember_turn
│   ├── tools.py        # find_files, workspace roots
│   └── prefetch/       # Memory query strategies
├── classifier/         # Event classification (Tier 0/1/2)
│   └── worker.py       # Classification worker pool
├── core/               # Core capture, summarization, memory, storage
│   ├── screen_capture.py           # Main capture loop (separate process)
│   ├── screenshot_scheduler.py     # Screenshot timing and activity detection
│   ├── accessibility_text.py       # Platform-agnostic accessibility text extraction
│   ├── uia_worker.py               # Background accessibility worker
│   ├── screenshot_processor.py     # OCR and perceptual hashing
│   ├── ocr.py, ocr_crop.py         # RapidOCR integration
│   ├── summarizer.py               # Session summarization
│   ├── distil.py                   # Fact extraction from summaries
│   ├── memory_consolidation.py     # Candidate → claim pipeline
│   ├── memory_store.py             # Memory CRUD and intro builder
│   ├── storage.py                  # SQLite operations, schema migrations
│   ├── events.py                   # Event data classes
│   ├── paths.py                    # Data directory resolution
│   ├── platform_support.py         # OS detection, clipboard, window metadata
│   ├── privacy_settings.py         # Privacy toggle management
│   ├── secret_patterns.py          # Regex for API keys, tokens, passwords
│   ├── private_windows.py          # Private browsing detection
│   ├── cloud_egress.py             # MCP reply scrubbing
│   ├── ollama_client.py            # Ollama API client
│   ├── llm_gateway.py              # LLM request queue with priority
│   ├── chat_model.py               # Model name resolution
│   ├── model_residency.py          # Model warm/download status
│   ├── local_embeddings.py         # all-MiniLM-L6-v2 embedding
│   ├── image_embeddings.py         # (opt-in, default off)
│   ├── rag.py                      # Event RAG indexer (opt-in)
│   ├── background_jobs.py          # Background worker lifecycle
│   ├── performance_metrics.py      # CPU/memory telemetry
│   └── diagnostics.py              # /settings/diagnostics endpoint
├── electron-ui/        # Desktop app (Electron)
│   ├── electron/
│   │   ├── main.js                 # Main process entry point
│   │   ├── preload.js, setup-preload.js  # Renderer bridge scripts
│   │   └── lib/                    # Main process modules
│   │       ├── windows.js          # Window creation and lifecycle
│   │       ├── setup.js            # Setup wizard orchestration
│   │       ├── api-spawn.js        # Python API subprocess management
│   │       ├── mcp.js              # MCP config generation
│   │       ├── llm-config.js       # Model selection persistence
│   │       ├── hardware.js         # RAM/VRAM detection
│   │       ├── paths.js            # Electron path resolution
│   │       ├── updates.js          # Update checks (placeholder)
│   │       └── app-icons.js        # Tray icon management
│   ├── src/
│   │   ├── index.html              # Main window (timeline view)
│   │   └── js/
│   │       ├── app.js              # Main UI controller
│   │       ├── dom.js              # DOM utilities
│   │       ├── dialogs.js          # Modal dialogs
│   │       ├── capture-ui.js       # Capture status indicator
│   │       └── markdown.js         # Markdown rendering (marked + DOMPurify)
│   ├── assets/                     # Icons and images
│   ├── nsis/                       # Windows installer scripts
│   └── package.json                # Electron build config (electron-builder)
├── tests/              # Regression test suite (pytest)
│   ├── test_runtime_regressions.py # Core functionality smoke tests
│   ├── test_memory_consolidation.py
│   ├── test_summarizer_*.py
│   ├── test_accessibility_text.py
│   ├── test_mcp_server.py
│   └── ...
├── scripts/            # Utilities and probe scripts
│   ├── clippy-mcp, clippy-mcp.cmd  # MCP server launchers
│   ├── probe_*.py                  # Diagnostic scripts
│   └── collect_github_traffic.ps1  # (disabled in fork)
├── docs/               # Documentation
│   ├── architecture.md
│   ├── usage.md
│   ├── mcp.md
│   └── grok-bot/       # Fork-specific docs
├── archive/            # Removed features (in-app chat, query router, prefetch)
├── stats/              # GitHub traffic snapshots (not updated in fork)
├── api_server.py       # FastAPI entry point
├── mcp_server.py       # MCP server entry point
├── requirements.txt    # Python dependencies
├── pyproject.toml      # Python package config
└── README.md
```

---

## Core Modules

### Capture

- **`core/screen_capture.py`** - Main capture loop, runs as separate process
  - Keyboard listener (pynput)
  - Clipboard monitor
  - Foreground window polling
  - Calls `screenshot_scheduler.py` for timing decisions
- **`core/screenshot_scheduler.py`** - Screenshot timing, activity debounce, typing burst detection
- **`core/accessibility_text.py`** - Platform-agnostic entry for UI tree walks
- **`core/uia_worker.py`** - Background thread for slow accessibility walks (Windows UI Automation)
- **`core/mac_ui.py`** - macOS AX API implementation (AXUIElement, System Events fallback)
- **`core/editor_accessibility.py`** - VS Code / Cursor screen-reader enablement
- **`classifier/worker.py`** - Three-tier classification (rule-based, feature-based, LLM)

### Summarization & Memory

- **`core/summarizer.py`** - 60-second tick, groups events into sessions, calls chat model
- **`core/distil.py`** - Fact extraction from summaries (runs every 5 sessions)
- **`core/memory_consolidation.py`** - Candidate → fact pipeline, cluster routing, conflict detection
- **`core/memory_store.py`** - Memory CRUD, intro builder, identity field management
- **`core/intro_builder.py`** - Weekly intro refresh daemon

### Storage & Search

- **`core/storage.py`** - SQLite operations, schema migrations, FTS5 indexes
- **`core/screenshot_search.py`** - Screenshot full-text search
- **`core/screenshot_files.py`** - JPEG filename resolution and purging
- **`core/screenshot_ttl.py`** - Retention policy enforcement
- **`core/timeline_groups.py`** - Session grouping by similarity

### LLM & Embeddings

- **`core/ollama_client.py`** - Ollama API client (requests, streaming)
- **`core/llm_gateway.py`** - Request queue with priority (high/low/background)
- **`core/chat_model.py`** - Model name resolution (`CLIPPY_CHAT_MODEL` env, `llm_config.json`)
- **`core/model_residency.py`** - Track which models are warm in Ollama
- **`core/model_download.py`** - Hugging Face model downloader
- **`core/local_embeddings.py`** - `all-MiniLM-L6-v2` embedding (sentence-transformers)
- **`core/image_embeddings.py`** - Screenshot embeddings (opt-in, default off)
- **`core/rag.py`** - Event RAG indexer (opt-in, default off)

### Privacy & Security

- **`core/privacy_settings.py`** - Privacy toggle management (per-app, private browsing)
- **`core/secret_patterns.py`** - Regex patterns for API keys, tokens, passwords
- **`core/secret_fields.py`** - Password field detection heuristics
- **`core/private_windows.py`** - Private browsing detection (Chrome, Edge, Brave)
- **`core/cloud_egress.py`** - MCP reply scrubbing before cloud client sees it

### Platform Support

- **`core/platform_support.py`** - OS detection, clipboard, window metadata, process priority
- **`core/process_names.py`** - Process name normalization
- **Windows:** `pywin32`, `uiautomation`, `win32gui`, `win32process`
- **macOS:** `pyobjc-framework-Quartz`, `pyobjc-framework-Cocoa`, `pyobjc-framework-ApplicationServices`

---

## Entry Points

### Desktop App

```bash
cd electron-ui
npm install
npm start       # Launch Electron app (dev mode)
npm run dist    # Build installer (Windows: .exe, macOS: .dmg)
```

**Main process:** `electron-ui/electron/main.js`
- Spawns Python API server (`api_server.py`)
- Spawns capture process (`core/screen_capture.py`)
- Manages Ollama lifecycle (if bundled or user-installed)
- Creates tray icon, main window, setup wizard

**Renderer:** `electron-ui/src/index.html` + `src/js/app.js`

### Python API Server

```bash
python api_server.py
# Or with custom port:
CLIPPY_API_PORT=8000 python api_server.py
```

**Listens on:** `127.0.0.1:<port>` (loopback only)

### MCP Server

```bash
python mcp_server.py
# Or via launcher:
./scripts/clippy-mcp        # Unix
./scripts/clippy-mcp.cmd    # Windows
```

**Protocol:** MCP over stdio (launched by MCP client)

### Capture Process (standalone)

```bash
python core/screen_capture.py
```

Normally spawned by Electron, but can run standalone for testing.

---

## Storage & Schema

**Database:** `core/data/events.db` (dev) or `%APPDATA%\Clippy Vision\data\events.db` (Windows) / `~/Library/Application Support/Clippy Vision/data/events.db` (macOS)

**Mode:** WAL (Write-Ahead Logging) for concurrent reads

### Tables

#### `events`
- **Purpose:** Raw captured events (context_change, screenshot_analysis, paste, clipboard_change, typing_burst)
- **Key columns:** `event_id`, `timestamp`, `event_type`, `window_title`, `process_name`, `url`, `text_content`, `screen_text`, `clipboard_text`, `classification`, `interest_score`, `screenshot`, `session_id`
- **Retention:** 7 days default (1-30 configurable)
- **FTS5 index:** `events_fts` on `window_title`, `process_name`, `url`, `text_content`, `screen_text`

#### `sessions`
- **Purpose:** Session summaries (output of summarizer)
- **Key columns:** `summary_id`, `session_id`, `start_time`, `end_time`, `summary`, `active_task`, `entities`, `app_names`, `event_count`, `vector_embedding`
- **Retention:** 90 days default (1-180 configurable)
- **FTS5 index:** `sessions_fts` on `summary`, `active_task`, `entities`, `app_names`

#### `memory_facts`
- **Purpose:** Durable behavioral claims (confirmed patterns)
- **Key columns:** `fact_id`, `fact_text`, `vector_embedding`, `cluster_id`, `session_ids`, `first_seen`, `last_confirmed`, `seen_count`, `confidence`, `source`, `status`
- **Retention:** Until user deletes

#### `memory_candidates`
- **Purpose:** Single-sitting observations (not yet facts)
- **Key columns:** `candidate_id`, `text`, `vector_embedding`, `session_ids`, `local_day`, `status`, `seen_count`
- **Status:** `open`, `promoted`, `absorbed`, `dropped`, `flagged`

#### `memory_clusters`
- **Purpose:** Cluster metadata for fact grouping
- **Key columns:** `cluster_id`, `centroid_embedding`, `fact_ids`, `updated_at`

#### `memory_conflicts`
- **Purpose:** Unresolved fact contradictions
- **Key columns:** `conflict_id`, `fact_id_1`, `fact_id_2`, `reason`, `detected_at`

#### `memory_meta`
- **Purpose:** Distiller state, last intro refresh
- **Key columns:** `key`, `value`

#### `user_profile`
- **Purpose:** User name and identity fields
- **Key columns:** `key`, `value`, `source`, `updated_at`

#### `conversations`
- **Purpose:** Archived in-app chat history (no new writes)
- **Key columns:** `conversation_id`, `created_at`, `title`, `pinned`

### Indexes

- FTS5 virtual tables for full-text search on `events` and `sessions`
- Timestamps indexed for range queries
- `session_id` indexed for joins

---

## Platform Support

### Windows (Primary)

**Status:** Fully supported (v2.0.0)

**Capture:**
- Screenshots: `mss`
- Accessibility: `pywin32` + `uiautomation` (UI Automation)
- Keyboard: `pynput`
- Clipboard: `win32clipboard`
- Window metadata: `win32gui`, `win32process`

**Privacy:**
- Password fields: UI Automation `IsPassword` property
- Private browsing: Chrome, Edge, Brave (class name `Chrome_WidgetWin_1` + `--app-id` check)

**Installer:** NSIS (`.exe`), unsigned

### macOS

**Status:** Partially supported (v1.3.1 installers, v2.0.0 validation pending)

**Capture:**
- Screenshots: `Quartz.CGWindowListCreateImage`
- Accessibility: `ApplicationServices.AXUIElement` + System Events fallback
- Keyboard: `pynput`
- Clipboard: `AppKit.NSPasteboard`
- Window metadata: `Quartz.CGWindowListCopyWindowInfo`

**Privacy:**
- Password fields: `AXSecureTextField` role
- Private browsing: Chrome, Edge, Brave (`--app-id` in window title or command-line args)

**Installer:** DMG (arm64, x64), unsigned

**Permissions required:**
- Screen Recording (`NSScreenCaptureUsageDescription`)
- Accessibility (`NSAccessibilityUsageDescription`)

### Linux

**Status:** Not supported

**Known gaps:**
- No Linux-specific accessibility API integration
- Window metadata, clipboard, keyboard would need X11/Wayland implementations
- Packaging (AppImage, .deb, .rpm) not set up

**Blockers:**
- `core/platform_support.py` assumes Windows or macOS
- `core/accessibility_text.py` has no Linux fallback
- Installer scripts only for Windows (NSIS) and macOS (DMG)

---

## Testing

### Test Suite

**Framework:** pytest

**Location:** `tests/`

**Run:**
```bash
pytest                          # All tests
pytest tests/test_mcp_server.py # Single file
pytest -v                       # Verbose
pytest -k memory                # Filter by keyword
```

**Key tests:**
- `test_runtime_regressions.py` - Core functionality smoke tests (classification, summarization, storage)
- `test_memory_consolidation.py` - Candidate/fact pipeline, conflict detection
- `test_summarizer_*.py` - Session grouping, deduplication, refresh logic
- `test_accessibility_text.py` - Windows UI Automation, macOS AX API
- `test_mcp_server.py` - MCP tool schemas and basic calls
- `test_private_windows.py` - Private browsing detection
- `test_editor_accessibility.py` - VS Code screen-reader enablement

**Coverage:** Core logic well-covered, Electron UI untested

**Fixtures:** Tests use in-memory SQLite (`:memory:`) or temporary databases

### Manual Testing

**Installation test:** `test_installation.py` (run after build, checks Python, Ollama, model pull)

**Diagnostic scripts:**
- `scripts/probe_ocr.py` - Test RapidOCR on a screenshot
- `scripts/probe_accessibility.py` - Dump accessibility tree for foreground window
- `scripts/probe_privacy_redact.py` - Test password field detection
- `scripts/dump_cursor_a11y.py` - Dump Cursor editor accessibility state
- `scripts/probe_queues.py` - Inspect background job queues

---

## Building & Packaging

### Dependencies

**Python:** 3.12+ recommended

**Node.js:** 20+ (for Electron)

**Ollama:** Required at runtime (bundled or user-installed)

### Build from Source

```bash
# Python dependencies
pip install -r requirements.txt

# Electron app
cd electron-ui
npm install
npm start                # Dev mode
npm run dist             # Build installer (Windows or macOS)
```

### Installer Output

**Windows:** `electron-ui/dist/ClippyVision-Windows-Setup-{version}.exe`

**macOS:** `electron-ui/dist/ClippyVision-macOS-{arch}-{version}.dmg`

### Packaging Notes

- Python code bundled in `extraResources/clippy/` inside `.asar`
- Ollama bundled on Windows (portable exe), user-installed on macOS
- Models (`qwen3:8b`, `all-MiniLM-L6-v2`) downloaded on first run, not bundled
- Installer unsigned (Windows: "More info → Run anyway", macOS: right-click → Open)

### CI/CD

**Workflows:**
- `.github/workflows/release.yml` - Build and upload installers on tag push or manual dispatch
- `.github/workflows/update-contributors.yml` - Auto-refresh contributor list
- `.github/workflows/collect-github-traffic.yml` - ~~Disabled in fork~~ (scheduled commits to main)

**Release process:**
1. Tag version: `git tag v2.0.1 && git push --tags`
2. Workflow builds Windows installer, attaches to GitHub release
3. macOS installers opt-in via manual dispatch (validation pending)

---

## Known Gaps & Tech Debt

### High Priority

1. **Linux support completely missing**
   - No accessibility API integration
   - No window metadata, clipboard, or keyboard implementations
   - Would need X11/Wayland platform-specific code

2. **macOS 2.0 installers not validated**
   - v2.0.0 Windows-only release
   - macOS users stuck on v1.3.1 until validation completes

3. **Installers unsigned**
   - Windows SmartScreen warnings
   - macOS Gatekeeper blocks (requires right-click → Open)
   - Code signing certificate needed (~$500/year)

4. **Privacy redaction is best-effort, not guaranteed**
   - Password field detection heuristics can miss some fields
   - Private browsing covers Chrome, Edge, Brave, Firefox (Windows), Opera (Windows), Vivaldi (Windows); Safari not covered on macOS
   - Secret regex patterns may not catch all token formats

5. **No built-in chat UI**
   - Requires external MCP client (Cursor, Claude Desktop, VS Code)
   - In-app chat removed in v2.0.0 (archived in `archive/in_app_chat/`)
   - High onboarding friction for non-technical users

### Medium Priority

6. **Performance overhead not quantified**
   - `core/performance_metrics.py` tracks CPU/memory but no published benchmarks
   - Accessibility walks can lag on complex UIs (VS Code, JetBrains IDEs)
   - Screenshot scheduler adaptive, but no user control over aggressiveness

7. **No Linux packaging**
   - No AppImage, .deb, or .rpm builds
   - Manual setup required (Python, Ollama, dependencies)

8. **No audio capture**
   - Meeting transcription planned but not implemented
   - Would need faster-whisper or whisper.cpp integration
   - macOS system audio capture complex (ScreenCaptureKit or virtual device)

9. **Model download UX rough**
   - First run downloads ~5 GB (`qwen3:8b` + `all-MiniLM-L6-v2`)
   - No progress bar, no pause/resume
   - Ollama auto-pull blocks if model name typo

10. **RAG and image embeddings opt-in, default off**
    - `core/rag.py` event indexer exists but disabled
    - `core/image_embeddings.py` screenshot embeddings disabled
    - Disk space, memory, and speed concerns cited in comments

### Low Priority

11. **Archived features in repo, not removed**
    - `archive/` directory: query router, prefetch strategies, in-app chat
    - Git history bloat (~30 MB)
    - Could extract to separate repo

12. **Classifier Tier 2 (LLM) slow**
    - Queues 4-event context to chat model for edge cases
    - Adds ~500ms latency per uncertain event
    - Could batch or cache verdicts

13. **No data export/import UI**
    - `/settings/data/export` API endpoint exists
    - No UI to download JSON
    - No import from backup

14. **Test coverage uneven**
    - Core logic well-tested
    - Electron UI untested (no E2E framework)
    - Platform-specific code (macOS) thin on tests

15. **GitHub Actions traffic workflow disabled**
    - `.github/workflows/collect-github-traffic.yml` scheduled daily commits
    - Disabled in fork to avoid noise
    - Upstream repo still uses it

### Risks

- **SQLite corruption** - WAL mode mitigates, but no automatic repair
- **Ollama crashes** - No restart logic, capture continues but summarizer stalls
- **Accessibility API hangs** - Background worker timeout exists (10s), but some apps (IntelliJ) can deadlock
- **Memory leaks in long-running capture process** - No systematic profiling, anecdotal reports of growth over days

### Couldn't Verify

- **Windows 10 vs 11 differences** - Docs claim support for both, but testing coverage unclear
- **Multi-monitor behavior** - Code references `capture_all_monitors` setting, but behavior not documented
- **Model size limits** - Setup wizard checks RAM/VRAM, but edge cases (swap, overcommit) not tested
- **MCP client compatibility** - Claims Cursor, Claude Desktop, VS Code, JetBrains, etc., but only Cursor and Claude Desktop explicitly tested upstream

---

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for setup steps, building from source, and good first issues.

**Quick start:**
```bash
git clone https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT.git
cd Clippy-vision_RAN_BY_GROK_BOT
cd electron-ui
npm install
npm start  # Setup wizard runs on first launch
```

**Test:**
```bash
pip install -r requirements.txt
pytest
```

**Probe:**
```bash
python scripts/probe_ocr.py <screenshot.jpg>
python scripts/probe_accessibility.py
```

---

**Document status:** Living document. Update when architecture changes.
