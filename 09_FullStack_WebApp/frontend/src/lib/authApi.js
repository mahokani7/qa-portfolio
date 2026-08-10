const AUTH_MOCK_STORAGE_KEY = 'todo-app.mock-users'
const shouldUseMockAuth = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_AUTH !== 'false'

function getMockUsers() {
  const storedUsers = window.localStorage.getItem(AUTH_MOCK_STORAGE_KEY)

  if (!storedUsers) {
    return []
  }

  try {
    return JSON.parse(storedUsers)
  } catch {
    window.localStorage.removeItem(AUTH_MOCK_STORAGE_KEY)
    return []
  }
}

function setMockUsers(users) {
  window.localStorage.setItem(AUTH_MOCK_STORAGE_KEY, JSON.stringify(users))
}

function normalizeIdentity(value) {
  return value.trim().toLowerCase()
}

function buildMockAuthResult(user, message) {
  return {
    message,
    user: {
      id: user.id,
      name: user.name,
      email: user.email,
    },
  }
}

async function loginWithMock(credentials) {
  const normalizedUsername = normalizeIdentity(credentials.username)
  const matchedUser = getMockUsers().find((user) => {
    return user.name.toLowerCase() === normalizedUsername || user.email === normalizedUsername
  })

  if (!matchedUser || matchedUser.password !== credentials.password) {
    throw new Error('사용자 이름 또는 비밀번호가 올바르지 않습니다.')
  }

  return buildMockAuthResult(matchedUser, '로그인되었습니다.')
}

async function registerWithMock(credentials) {
  const name = credentials.name.trim()
  const email = normalizeIdentity(credentials.email)
  const existingUsers = getMockUsers()

  if (existingUsers.some((user) => user.email === email)) {
    throw new Error('A user with that email already exists.')
  }

  if (existingUsers.some((user) => user.name.toLowerCase() === name.toLowerCase())) {
    throw new Error('A user with that user name already exists.')
  }

  const nextUser = {
    id: crypto.randomUUID(),
    name,
    email,
    password: credentials.password,
  }

  setMockUsers([...existingUsers, nextUser])

  return buildMockAuthResult(nextUser, '회원가입이 완료되었습니다.')
}

export async function login(credentials) {
  let response

  try {
    response = await fetch('/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    })
  } catch {
    if (shouldUseMockAuth) {
      return loginWithMock(credentials)
    }

    throw new Error('백엔드 로그인 서버에 연결할 수 없습니다. MongoDB와 backend를 먼저 실행하세요.')
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    if (response.status === 502 || response.status === 503) {
      if (shouldUseMockAuth) {
        return loginWithMock(credentials)
      }

      throw new Error('백엔드 로그인 서버에 연결할 수 없습니다. MongoDB와 backend를 먼저 실행하세요.')
    }

    throw new Error(data?.message || '로그인에 실패했습니다.')
  }

  return data
}

export async function register(credentials) {
  let response

  try {
    response = await fetch('/api/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: credentials.name,
        email: credentials.email,
        password: credentials.password,
      }),
    })
  } catch {
    if (shouldUseMockAuth) {
      return registerWithMock(credentials)
    }

    throw new Error('백엔드 회원가입 서버에 연결할 수 없습니다. MongoDB와 backend를 먼저 실행하세요.')
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    if (response.status === 502 || response.status === 503) {
      if (shouldUseMockAuth) {
        return registerWithMock(credentials)
      }

      throw new Error('백엔드 회원가입 서버에 연결할 수 없습니다. MongoDB와 backend를 먼저 실행하세요.')
    }

    throw new Error(data?.message || '회원가입에 실패했습니다.')
  }

  return data
}
