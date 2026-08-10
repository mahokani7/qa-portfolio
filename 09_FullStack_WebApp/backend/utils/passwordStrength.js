const MIN_PASSWORD_LENGTH = 8
const MAX_PASSWORD_LENGTH = 128
const UPPERCASE_PATTERN = /[A-Z]/
const LOWERCASE_PATTERN = /[a-z]/
const DIGIT_PATTERN = /\d/
const SPECIAL_CHARACTER_PATTERN = /[^A-Za-z0-9]/

export function validatePasswordStrength(password) {
  const errors = []

  if (typeof password !== 'string' || password.length === 0) {
    errors.push('Password is required.')
    return {
      isValid: false,
      errors,
    }
  }

  if (password.length < MIN_PASSWORD_LENGTH) {
    errors.push(`Password must be at least ${MIN_PASSWORD_LENGTH} characters long.`)
  }

  if (password.length > MAX_PASSWORD_LENGTH) {
    errors.push(`Password must be no more than ${MAX_PASSWORD_LENGTH} characters long.`)
  }

  if (!UPPERCASE_PATTERN.test(password)) {
    errors.push('Password must include at least one uppercase letter.')
  }

  if (!LOWERCASE_PATTERN.test(password)) {
    errors.push('Password must include at least one lowercase letter.')
  }

  if (!DIGIT_PATTERN.test(password)) {
    errors.push('Password must include at least one number.')
  }

  if (!SPECIAL_CHARACTER_PATTERN.test(password)) {
    errors.push('Password must include at least one special character.')
  }

  return {
    isValid: errors.length === 0,
    errors,
  }
}

export { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH }