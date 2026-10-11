# Release Workflow Audit & Changes Summary

This document provides a detailed explanation of all changes made to the release workflow, why they were made, and what was removed or gated.

## Workflow Files Modified

### `.github/workflows/release.yml`

**Original state:** Inherited from upstream Clippy Vision, designed for Windows and macOS builds only.

**New state:** Supports Windows, macOS (opt-in), and Linux AppImage builds, all as DRAFT releases, with dry-run testing capability.

---

## Detailed Change Breakdown

### 1. Workflow Triggers (Lines 1-16)

#### Changes Made:
```yaml
# BEFORE:
workflow_dispatch:
  inputs:
    tag:
      description: 'Existing release tag to build and attach installers to (e.g. v2.0.0)'
      required: true
    include_macos:
      description: 'Also build and upload macOS installers (only after Apple Silicon and Intel validation)'
      type: boolean
      default: false

# AFTER:
workflow_dispatch:
  inputs:
    tag:
      description: 'Release tag to build (e.g. v2.0.1). Leave empty for dry-run without creating a release.'
      required: false  # Changed from required: true
    include_macos:
      description: 'Also build unsigned macOS installers (opt-in, manual validation required)'
      type: boolean
      default: false
    include_linux:  # NEW
      description: 'Build Linux AppImage (enabled by default for tag pushes)'
      type: boolean
      default: true
```

#### Why Changed:
- **`tag` made optional:** Allows workflow_dispatch to run without a tag for dry-run testing (builds artifacts, doesn't create a release)
- **`include_linux` added:** Allows opting out of Linux builds in workflow_dispatch (default: true)
- **Description updated:** Clarifies that macOS installers are unsigned and dry-run mode is available

#### Cost Impact:
- ✅ **Zero cost** — All inputs use free GitHub features

---

### 2. Windows Job (Lines 20-66)

#### Changes Made:

**Step: "Sync app version from release tag or dry-run" (Lines 42-63)**

```bash
# NEW LOGIC:
if [[ -n "${{ github.event.inputs.tag }}" ]]; then
  TAG="${{ github.event.inputs.tag }}"
elif [[ "${{ github.ref_type }}" == "tag" ]]; then
  TAG="${{ github.ref_name }}"
else
  # Dry-run: use package.json version with -dev suffix
  TAG="v$(node -p "require('./package.json').version")-dev+${{ github.sha }}"
  echo "::notice::Dry-run build (no release will be created): $TAG"
fi
```

**Why:** Supports three modes:
1. **Tag push:** Uses `github.ref_name` (e.g., `v2.1.0`)
2. **workflow_dispatch with tag:** Uses provided `tag` input
3. **workflow_dispatch without tag:** Dry-run mode with `-dev+<sha>` suffix (e.g., `v2.0.0-dev+abc1234`)

**Step: "Build Windows installer (unsigned)" (Line 65)**
- ✅ **No change** — Already unsigned (upstream never configured signing certs)
- ✅ **Cost:** Zero (no signing service)

**NEW Step: "Upload Windows installer artifact" (Lines 67-72)**
```yaml
- name: Upload Windows installer artifact
  uses: actions/upload-artifact@v4
  with:
    name: windows-installer
    path: electron-ui/dist/*.exe
    retention-days: 14
```

**Why Added:**
- Allows downloading installers from workflow runs even in dry-run mode (no release created)
- 14-day retention (free tier)

**Step: "Upload Windows installer to release" (Lines 74-83)**

```yaml
# ADDED:
if: github.event.inputs.tag != '' || github.ref_type == 'tag'
# ADDED:
draft: true
prerelease: false
```

**Why Changed:**
- **Conditional:** Only creates/updates release if tag exists (skips in dry-run mode)
- **`draft: true`:** Releases require manual review and publishing (prevent accidental public releases)
- **`prerelease: false`:** Not marked as pre-release by default

#### Cost Impact:
- ✅ **Zero cost** — GitHub-hosted `windows-latest` runner (free), artifact storage within free tier

---

### 3. macOS Job (Lines 68-112)

#### Changes Made:

**Step: "Sync app version from release tag or dry-run" (Lines 86-100)**
- Same logic as Windows job (supports dry-run mode)

**Step: "Build macOS installer (unsigned, code signing disabled)" (Line 102)**
```yaml
env:
  CSC_IDENTITY_AUTO_DISCOVERY: false  # Already existed
```

- ✅ **No change** — Already unsigned (upstream already disabled auto-discovery)
- ✅ **Cost:** Zero (no Apple Developer account, no notarization service)

**Why This Works:**
- `electron-builder` respects `CSC_IDENTITY_AUTO_DISCOVERY: false` and builds unsigned `.dmg` files
- No secrets or certificates required

**NEW Step: "Upload macOS installers artifact" (Lines 105-110)**
- Same as Windows artifact upload

**Step: "Upload macOS installers to release" (Lines 112-121)**
```yaml
# ADDED:
if: github.event.inputs.tag != ''  # Only upload if tag provided
# ADDED:
draft: true
prerelease: false
```

**Why Changed:**
- macOS builds are **opt-in only** (never run on tag pushes), so only upload if explicit tag provided
- Same DRAFT logic as Windows

#### Cost Impact:
- ✅ **Zero cost** — GitHub-hosted `macos-latest` runner (free), artifact storage within free tier
- ⚠️ **Opt-in only** — Does not run unless explicitly requested (saves runner minutes)

---

### 4. Linux Job (Lines 123-176) — **NEW**

#### Full Job Configuration:

```yaml
build-linux:
  # Run on tag pushes, or on workflow_dispatch if include_linux is true (default)
  if: github.event_name == 'push' || (github.event_name == 'workflow_dispatch' && inputs.include_linux)
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        lfs: true

    - name: Set up Node
      uses: actions/setup-node@v4
      with:
        node-version: 20

    - name: Install dependencies
      working-directory: electron-ui
      run: npm ci

    - name: Sync app version from release tag or dry-run
      working-directory: electron-ui
      shell: bash
      run: |
        if [[ -n "${{ github.event.inputs.tag }}" ]]; then
          TAG="${{ github.event.inputs.tag }}"
        elif [[ "${{ github.ref_type }}" == "tag" ]]; then
          TAG="${{ github.ref_name }}"
        else
          # Dry-run: use package.json version with -dev suffix
          TAG="v$(node -p "require('./package.json').version")-dev+${{ github.sha }}"
          echo "::notice::Dry-run build (no release will be created): $TAG"
        fi
        VERSION="${TAG#v}"
        if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.+-].*)?$ ]]; then
          echo "Invalid version derived from tag '$TAG' (got '$VERSION')"
          exit 1
        fi
        npm version "$VERSION" --no-git-tag-version --allow-same-version
        echo "Building Clippy Vision $VERSION (release tag $TAG)"
        echo "VERSION=$VERSION" >> $GITHUB_ENV
        echo "TAG=$TAG" >> $GITHUB_ENV

    - name: Build Linux AppImage (unsigned)
      working-directory: electron-ui
      run: npm run dist:linux

    - name: Upload Linux AppImage artifact
      uses: actions/upload-artifact@v4
      with:
        name: linux-appimage
        path: electron-ui/dist/*.AppImage
        retention-days: 14

    - name: Upload Linux AppImage to release
      # Only upload to release if we have a tag (not a dry-run)
      if: github.event.inputs.tag != '' || github.ref_type == 'tag'
      uses: softprops/action-gh-release@v2
      with:
        tag_name: ${{ github.event.inputs.tag || github.ref_name }}
        files: |
          electron-ui/dist/*.AppImage
        draft: true
        prerelease: false
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

#### Why Added:
- **Linux support is new in this fork** (PRs #10, #14) — Release workflow must support it
- **AppImage chosen** because:
  - Single-file portable format (no installation required)
  - No code signing required or available
  - Works across distros
  - `electron-builder` has built-in AppImage support

#### Configuration Details:

**Job condition:**
```yaml
if: github.event_name == 'push' || (github.event_name == 'workflow_dispatch' && inputs.include_linux)
```
- Runs on tag pushes by default
- Runs on workflow_dispatch if `include_linux` is true (default)
- Can opt-out with `include_linux: false`

**Build step:**
```bash
npm run dist:linux
```
- Uses `electron-builder --linux` (defined in `package.json`)
- Builds AppImage x64 only (no arm64, no deb/rpm yet)
- Unsigned (no code signing)

**Artifact upload:**
- Same pattern as Windows/macOS
- 14-day retention

**Release upload:**
- Same conditional logic (skips in dry-run mode)
- Same DRAFT setting

#### Cost Impact:
- ✅ **Zero cost** — GitHub-hosted `ubuntu-latest` runner (free), artifact storage within free tier

---

## Package Configuration Changes

### `electron-ui/package.json`

#### Script Added:
```json
"dist:linux": "electron-builder --linux"
```

**Why:** Provides a npm script for building Linux AppImage (consistent with `dist:win` and `dist:mac` patterns)

#### Build Configuration Added:
```json
"linux": {
  "target": [
    {
      "target": "AppImage",
      "arch": ["x64"]
    }
  ],
  "icon": "assets/icon.png",
  "category": "Utility",
  "artifactName": "ClippyVision-Linux-${arch}-${version}.${ext}",
  "desktop": {
    "Name": "Clippy Vision",
    "Comment": "Local AI desktop companion with screen awareness",
    "Categories": "Utility;Office;",
    "StartupWMClass": "clippy-vision"
  }
}
```

**Why:**
- **Target AppImage x64:** Single portable format, no installation required
- **Icon:** Reuses existing `assets/icon.png`
- **Category Utility:** Matches application purpose
- **Desktop entry:** Provides proper XDG .desktop file metadata
- **StartupWMClass:** Helps window managers group app windows correctly

#### Cost Impact:
- ✅ **Zero cost** — All configuration is free

---

## Upstream Dependencies Removed or Gated

### Analysis:
❌ **None found**

**Why:** Upstream workflow was already clean:
- No code signing certificates configured
- No notarization service configured
- No upstream-only secrets referenced
- `CSC_IDENTITY_AUTO_DISCOVERY: false` already present (disables auto-signing)
- No paid services used

### What We Did NOT Need to Remove:
- ❌ Signing certificates (never configured)
- ❌ Notarization steps (never present)
- ❌ Apple credentials (never used)
- ❌ Windows signing services (never configured)
- ❌ Paid build services (never used)

---

## Workflow Modes Summary

### Mode 1: Tag Push (e.g., `git tag v2.1.0 && git push origin v2.1.0`)

**Triggers:** `on.push.tags: v*`

**What Runs:**
- ✅ `build-windows` — Builds Windows installer
- ✅ `build-linux` — Builds Linux AppImage
- ❌ `build-macos` — Skipped (opt-in only)

**What Gets Created:**
- ✅ DRAFT GitHub release `v2.1.0`
- ✅ Windows `.exe` attached to release
- ✅ Linux `.AppImage` attached to release
- ✅ Artifacts uploaded to workflow run (14-day retention)

**Cost:** ~5-8 minutes of GitHub-hosted runner time (free tier)

---

### Mode 2: workflow_dispatch with Tag (Manual release for existing tag)

**How to Trigger:**
1. Actions → Build & Publish Release → Run workflow
2. Select branch (e.g., `main`)
3. Enter tag: `v2.1.0`
4. (Optional) Check `include_macos: true` to also build macOS
5. Click "Run workflow"

**What Runs:**
- ✅ `build-windows` — Builds for specified tag
- ✅ `build-linux` — Builds for specified tag (unless `include_linux: false`)
- ✅ `build-macos` — Only if `include_macos: true`

**What Gets Created:**
- ✅ Updates existing DRAFT release `v2.1.0` (or creates if missing)
- ✅ Attaches installers to that release
- ✅ Artifacts uploaded to workflow run

**Cost:** Depends on options:
- Windows + Linux: ~5-8 minutes
- + macOS: ~10-15 minutes total

---

### Mode 3: workflow_dispatch Dry-Run (No tag, testing only)

**How to Trigger:**
1. Actions → Build & Publish Release → Run workflow
2. Select branch (e.g., `cursor/release-engineering-0d5a`)
3. **Leave "Release tag to build" empty**
4. (Optional) Adjust `include_linux` / `include_macos`
5. Click "Run workflow"

**What Runs:**
- ✅ `build-windows` — Builds with `-dev+<sha>` version
- ✅ `build-linux` — Builds with `-dev+<sha>` version (unless opted out)
- ✅ `build-macos` — Only if `include_macos: true`

**What Gets Created:**
- ✅ Artifacts uploaded to workflow run ONLY
- ❌ No release created
- ❌ No tags pushed

**Version:** `v2.0.0-dev+d614670` (example)

**Use Case:** Validate build pipeline before tagging a real release

**Cost:** Same as Mode 2 (depends on options)

---

## Testing Status

### CI Tests (Python)
- ✅ **Test on ubuntu-latest:** PASSED (2m15s)
- ✅ **Test on windows-latest:** PASSED (3m46s)
- ✅ **GitGuardian Security Checks:** PASSED (1s)

**Link:** https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/actions/runs/38150449661

### Dry-Run Build Test
- ⚠️ **NOT YET TESTED** — Requires manual workflow_dispatch trigger

**How to Test:**
1. Go to: https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/actions/workflows/release.yml
2. Click "Run workflow"
3. Select branch: `cursor/release-engineering-0d5a`
4. Leave "Release tag to build" **empty**
5. Click "Run workflow"

**Expected Result:**
- ✅ Windows job builds `.exe` artifact
- ✅ Linux job builds `.AppImage` artifact
- ✅ Both artifacts available for download
- ✅ No release created

**If Build Fails:**
- Check workflow logs for errors
- Likely issues: `electron-builder` dependencies, Node.js version, packaging config

---

## Cost Analysis

### Runner Minutes Used Per Release:

| Job | Runner | Duration | Cost |
|-----|--------|----------|------|
| Windows | `windows-latest` | ~2-3 min | ✅ Free tier |
| Linux | `ubuntu-latest` | ~2-3 min | ✅ Free tier |
| macOS (opt-in) | `macos-latest` | ~5-7 min | ✅ Free tier |

**Total per release (Windows + Linux):** ~5-8 minutes  
**Total with macOS:** ~10-15 minutes

**GitHub Actions Free Tier:**
- Public repos: **Unlimited** minutes
- Private repos: 2,000 minutes/month (this repo is public)

### Storage Used:

| Resource | Size | Retention | Cost |
|----------|------|-----------|------|
| Artifacts | ~200-300 MB | 14 days | ✅ Free tier |
| Releases | ~200-300 MB | Permanent | ✅ Free (unlimited) |

**GitHub Storage Free Tier:**
- Artifacts: 500 MB (free tier, this usage is well below)
- Releases: **Unlimited** storage

### Secrets Required:
- ✅ `GITHUB_TOKEN` — Provided automatically by GitHub Actions

### External Services:
- ❌ None

---

## Security Considerations

### Code Signing:
- ❌ **Not implemented** — All installers are unsigned
- ⚠️ **Consequence:** OS warnings (SmartScreen, Gatekeeper)
- ✅ **Mitigation:** Clear installation instructions in release notes, SHA256 checksums

### Secrets:
- ✅ **No secrets required** beyond auto-provided `GITHUB_TOKEN`
- ✅ **No certificate files stored**
- ✅ **No API keys required**

### Release Publishing:
- ✅ **All releases created as DRAFT** (require manual publishing)
- ✅ **Prevents accidental public releases**
- ✅ **Allows manual review before publishing**

---

## Known Limitations

### Windows Installer:
- ⚠️ Unsigned — SmartScreen warning expected
- ✅ Installation instructions provided in release notes

### Linux AppImage:
- ⚠️ Unsigned — No code signing available for AppImage
- ⚠️ Requires `chmod +x` before first run
- ⚠️ Requires system dependencies (xdotool, xclip, etc.)
- ⚠️ Not tested on real Linux hardware (only CI with Xvfb)

### macOS Installer:
- ⚠️ Unsigned — Gatekeeper will block by default
- ⚠️ Opt-in only (not built on tag pushes)
- ⚠️ Requires manual validation before upload
- ✅ Installation instructions provided (xattr workaround)

---

## Proposed Version

**`v2.1.0`**

**Rationale:**
- Fork point: upstream v2.0.0
- New features: Linux support, browser privacy detection, CI
- No breaking changes
- Semver: MINOR version bump

---

## Next Steps

1. ✅ **PR created:** #15
2. ✅ **CI passed:** All tests green
3. ⚠️ **Test dry-run build** (manual trigger required)
4. ⏳ **Review release notes:** `docs/release-notes/vNEXT.md`
5. ⏳ **Merge PR**
6. ⏳ **Test workflow_dispatch dry-run** (validate Windows + Linux builds)
7. ⏳ **Tag release:** `git tag v2.1.0 && git push origin v2.1.0`
8. ⏳ **Verify draft release created**
9. ⏳ **Publish release**

---

## References

- **PR:** https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/pull/15
- **Workflow file:** `.github/workflows/release.yml`
- **CHANGELOG:** `CHANGELOG.md`
- **Release notes:** `docs/release-notes/vNEXT.md`
- **CI run:** https://github.com/protocorn/Clippy-vision_RAN_BY_GROK_BOT/actions/runs/38150449661
