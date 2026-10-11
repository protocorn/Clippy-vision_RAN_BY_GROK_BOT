"""
Test OS check in hardware.js supports Linux as experimental platform.
"""
import json
import platform
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def hardware_js_path():
    """Return path to hardware.js."""
    repo_root = Path(__file__).parent.parent
    return repo_root / "electron-ui" / "electron" / "lib" / "hardware.js"


@pytest.fixture
def test_script(tmp_path, hardware_js_path):
    """Create a test Node.js script that uses hardware.js."""
    test_js = tmp_path / "test_os_check.js"
    test_js.write_text(f"""
const {{ createHardware }} = require('{hardware_js_path.as_posix()}');
const os = require('os');

// Mock dependencies
const paths = {{
    USER_DATA: '/tmp/test'
}};
const llmConfig = {{
    usesManagedOllama: () => false
}};
const runCommand = async () => ({{ code: 0, stdout: '', stderr: '' }});

const hardware = createHardware({{ paths, llmConfig, runCommand }});

async function test() {{
    const check = await hardware.getHardwareCheck();
    console.log(JSON.stringify({{
        platform: process.platform,
        osId: check.yours.os,
        osLabel: check.yours.osLabel,
        osGrade: check.grades.os,
        level: check.level
    }}, null, 2));
}}

test().catch(err => {{
    console.error(err);
    process.exit(1);
}});
""")
    return test_js


def test_os_check_passes_on_current_platform(test_script):
    """
    Test that the OS check passes on the current platform.
    
    This test runs on both Ubuntu and Windows in CI and verifies:
    - Windows passes with "Windows 10" or "Windows 11" label
    - Linux passes with "Linux (supported, experimental)" label
    """
    # Run the test script
    result = subprocess.run(
        ['node', str(test_script)],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    assert result.returncode == 0, f"Node script failed: {result.stderr}"
    
    # Parse the output
    output = json.loads(result.stdout)
    
    current_platform = platform.system().lower()
    
    # Verify OS grade is 'ok' (pass)
    assert output['osGrade'] == 'ok', (
        f"OS check should pass on {current_platform}, "
        f"but got grade '{output['osGrade']}'"
    )
    
    # Verify the OS label is appropriate for the platform
    if current_platform == 'windows':
        assert output['osLabel'] in ['Windows 10', 'Windows 11'], (
            f"Expected 'Windows 10' or 'Windows 11' label, got '{output['osLabel']}'"
        )
        assert output['platform'] == 'win32'
    
    elif current_platform == 'linux':
        assert output['osLabel'] == 'Linux (supported, experimental)', (
            f"Expected 'Linux (supported, experimental)' label, got '{output['osLabel']}'"
        )
        assert output['platform'] == 'linux'
        assert output['osId'] == 'linux'
    
    elif current_platform == 'darwin':
        assert 'macOS' in output['osLabel'], (
            f"Expected macOS label, got '{output['osLabel']}'"
        )
        assert output['platform'] == 'darwin'


def test_unsupported_os_behavior(tmp_path, hardware_js_path):
    """
    Test that unsupported OS platforms fail as expected.
    
    This test simulates an unsupported platform to ensure
    the check properly rejects platforms that aren't supported.
    """
    test_js = tmp_path / "test_unsupported_os.js"
    test_js.write_text(f"""
const {{ createHardware }} = require('{hardware_js_path.as_posix()}');

// Mock dependencies
const paths = {{
    USER_DATA: '/tmp/test'
}};
const llmConfig = {{
    usesManagedOllama: () => false
}};
const runCommand = async () => ({{ code: 0, stdout: '', stderr: '' }});

// Mock an unsupported platform
const originalPlatform = process.platform;
Object.defineProperty(process, 'platform', {{
    value: 'freebsd',
    writable: false,
    enumerable: true,
    configurable: true
}});

const hardware = createHardware({{ paths, llmConfig, runCommand }});

async function test() {{
    const check = await hardware.getHardwareCheck();
    console.log(JSON.stringify({{
        platform: process.platform,
        osGrade: check.grades.os,
        level: check.level
    }}, null, 2));
}}

test().catch(err => {{
    console.error(err);
    process.exit(1);
}});
""")
    
    # Run the test script
    result = subprocess.run(
        ['node', str(test_js)],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    assert result.returncode == 0, f"Node script failed: {result.stderr}"
    
    # Parse the output
    output = json.loads(result.stdout)
    
    # Verify unsupported OS fails
    assert output['osGrade'] == 'fail', (
        "Unsupported OS should fail the check"
    )
    assert output['level'] == 'block', (
        "Unsupported OS should be blocked from installation"
    )


def test_linux_experimental_note():
    """
    Verify that Linux shows as experimental in the label.
    
    This is a documentation test to ensure the experimental
    nature of Linux support is clear to users.
    """
    current_platform = platform.system().lower()
    
    if current_platform == 'linux':
        # If we're running on Linux, verify the label includes "experimental"
        # This test will only run on Ubuntu in CI
        pytest.skip("This test is verified by test_os_check_passes_on_current_platform on Linux")
    else:
        # On other platforms, this is a no-op but documents the requirement
        pass
