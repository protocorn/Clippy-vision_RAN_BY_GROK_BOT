/**
 * Setup preflight must require Python 3.11+.
 * Run with: node --test electron/lib/setup.test.js
 */
const { test } = require('node:test')
const assert = require('node:assert/strict')

const { evaluatePythonVersion } = require('./setup')

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
