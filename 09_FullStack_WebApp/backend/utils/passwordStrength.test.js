import test from 'node:test'
import assert from 'node:assert/strict'
import { MAX_PASSWORD_LENGTH, validatePasswordStrength } from './passwordStrength.js'

test('rejects an empty password', () => {
  const result = validatePasswordStrength('')

  assert.equal(result.isValid, false)
  assert.deepEqual(result.errors, ['Password is required.'])
})

test('rejects a very long password', () => {
  const password = `Aa1!${'x'.repeat(MAX_PASSWORD_LENGTH)}`
  const result = validatePasswordStrength(password)

  assert.equal(result.isValid, false)
  assert.ok(result.errors.includes(`Password must be no more than ${MAX_PASSWORD_LENGTH} characters long.`))
})

test('accepts a password with special characters when all requirements are met', () => {
  const result = validatePasswordStrength('Sup3r!Safe')

  assert.equal(result.isValid, true)
  assert.deepEqual(result.errors, [])
})

test('rejects a password without a special character', () => {
  const result = validatePasswordStrength('Sup3rSafe')

  assert.equal(result.isValid, false)
  assert.ok(result.errors.includes('Password must include at least one special character.'))
})

test('rejects a password without mixed case and a number', () => {
  const result = validatePasswordStrength('password!')

  assert.equal(result.isValid, false)
  assert.ok(result.errors.includes('Password must include at least one uppercase letter.'))
  assert.ok(result.errors.includes('Password must include at least one number.'))
})