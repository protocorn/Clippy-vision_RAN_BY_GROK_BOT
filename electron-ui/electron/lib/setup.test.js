/**
 * Setup preflight must require Python 3.11+.
 * Run with: node --test electron/lib/setup.test.js
 */
const { test } = require('node:test')
const assert = require('node:assert/strict')

const {
    evaluatePythonVersion,
    decideOllamaInstall,
    ollamaInstallCommandToRun,
    LINUX_OLLAMA_INSTALL_COMMAND,
    LINUX_OLLAMA_DOWNLOAD_URL,
} = require('./setup')

function collectInstallRuns(plan) {
    const invocation = ollamaInstallCommandToRun(plan)
    const runs = []
    if (invocation) runs.push([invocation.command, invocation.args])
    return runs
}

test('Python 3.9 is too old', () => {
    const result = evaluatePythonVersion('Python 3.9.18')
    assert.equal(result.ok, false)
    assert.equal(result.version, '3.9.18')
    assert.match(result.message, /Python 3\.9\.18 was found/)
    assert.match(result.message, /3\.11\+ is required/)
})

test('Python 3.10.x is too old', () => {
    const result = evaluatePythonVersion('Python 3.10.4')
    assert.equal(result.ok, false)
    assert.equal(result.version, '3.10.4')
    assert.match(result.message, /Python 3\.10\.4 was found/)
    assert.match(result.message, /3\.11\+ is required/)
})

test('Python 3.11.0 meets the minimum', () => {
    const result = evaluatePythonVersion('Python 3.11.0')
    assert.equal(result.ok, true)
    assert.equal(result.version, '3.11.0')
    assert.equal(result.message, null)
})

test('Python 3.12 meets the minimum', () => {
    const result = evaluatePythonVersion('Python 3.12')
    assert.equal(result.ok, true)
    assert.equal(result.version, '3.12')
})

test('Python 3.13 meets the minimum', () => {
    const result = evaluatePythonVersion('Python 3.13.1')
    assert.equal(result.ok, true)
    assert.equal(result.version, '3.13.1')
})

test('unparseable output reports a clear error', () => {
    const result = evaluatePythonVersion('not a version string')
    assert.equal(result.ok, false)
    assert.equal(result.version, null)
    assert.match(result.message, /Could not parse Python version/)
    assert.match(result.message, /3\.11\+ is required/)
})

test('linux without consent does not run an install command', () => {
    const plan = decideOllamaInstall({ platform: 'linux', userConsent: false })
    assert.equal(plan.action, 'linux-manual')
    assert.equal(plan.runInstall, false)
    assert.equal(plan.command, null)
    assert.equal(plan.officialCommand, LINUX_OLLAMA_INSTALL_COMMAND)
    assert.equal(plan.downloadUrl, LINUX_OLLAMA_DOWNLOAD_URL)
    assert.match(plan.instructions, /curl -fsSL https:\/\/ollama.com\/install.sh \| sh/)
    assert.match(plan.instructions, /https:\/\/ollama.com\/download\/linux/)
    assert.deepEqual(collectInstallRuns(plan), [])
    assert.equal(ollamaInstallCommandToRun(plan), null)
})

test('linux with consent plans pkexec for the official installer', () => {
    const plan = decideOllamaInstall({ platform: 'linux', userConsent: true })
    assert.equal(plan.action, 'linux-install')
    assert.equal(plan.runInstall, true)
    assert.equal(plan.command, 'pkexec')
    assert.equal(plan.officialCommand, LINUX_OLLAMA_INSTALL_COMMAND)
    assert.equal(plan.downloadUrl, LINUX_OLLAMA_DOWNLOAD_URL)
    const runs = collectInstallRuns(plan)
    assert.equal(runs.length, 1)
    assert.equal(runs[0][0], 'pkexec')
    assert.deepEqual(runs[0][1], ['sh', '-c', LINUX_OLLAMA_INSTALL_COMMAND])
    const invocation = ollamaInstallCommandToRun(plan)
    assert.equal(invocation.command, 'pkexec')
    assert.ok(invocation.args.join(' ').includes(LINUX_OLLAMA_INSTALL_COMMAND))
})

test('darwin uses Homebrew for a missing Ollama', () => {
    const plan = decideOllamaInstall({ platform: 'darwin', userConsent: false })
    assert.equal(plan.action, 'homebrew')
    assert.equal(plan.runInstall, true)
    assert.equal(plan.command, 'brew')
    assert.deepEqual(plan.args, ['install', 'ollama'])
    const runs = collectInstallRuns(plan)
    assert.equal(runs.length, 1)
    assert.equal(runs[0][0], 'brew')
    assert.deepEqual(runs[0][1], ['install', 'ollama'])
})

test('win32 uses winget for a missing Ollama', () => {
    const plan = decideOllamaInstall({ platform: 'win32', userConsent: false })
    assert.equal(plan.action, 'winget')
    assert.equal(plan.runInstall, true)
    assert.equal(plan.command, 'winget')
    assert.ok(plan.args.includes('Ollama.Ollama'))
    assert.ok(plan.args.includes('--silent'))
    const runs = collectInstallRuns(plan)
    assert.equal(runs.length, 1)
    assert.equal(runs[0][0], 'winget')
    assert.ok(runs[0][1].includes('Ollama.Ollama'))
})
