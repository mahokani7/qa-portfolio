const AUTH_SESSION_STORAGE_KEY = 'todo-app.auth-session'

export function getAuthSession() {
  const storedSession = window.sessionStorage.getItem(AUTH_SESSION_STORAGE_KEY)

  if (!storedSession) {
    return null
  }

  try {
    return JSON.parse(storedSession)
  } catch {
    window.sessionStorage.removeItem(AUTH_SESSION_STORAGE_KEY)
    return null
  }
}

export function setAuthSession(session) {
  window.sessionStorage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(session))
}

export function clearAuthSession() {
  window.sessionStorage.removeItem(AUTH_SESSION_STORAGE_KEY)
}