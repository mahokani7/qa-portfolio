const MOCK_TODOS_STORAGE_KEY = 'mock-todos'

const initialMockTodos = [
  {
    id: 'mock-1',
    title: '프런트엔드만으로 화면 확인하기',
    completed: false,
  },
  {
    id: 'mock-2',
    title: '백엔드 없이 할 일 추가 흐름 점검하기',
    completed: true,
  },
]

export const shouldUseMockApi =
  import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_API !== 'false'

async function getErrorMessage(response, fallbackMessage) {
  try {
    const errorBody = await response.json()

    if (typeof errorBody?.message === 'string' && errorBody.message) {
      return errorBody.message
    }
  } catch {
    return fallbackMessage
  }

  return fallbackMessage
}

function readMockTodos() {
  const storedTodos = window.localStorage.getItem(MOCK_TODOS_STORAGE_KEY)

  if (!storedTodos) {
    window.localStorage.setItem(MOCK_TODOS_STORAGE_KEY, JSON.stringify(initialMockTodos))
    return [...initialMockTodos]
  }

  try {
    const parsedTodos = JSON.parse(storedTodos)
    return Array.isArray(parsedTodos) ? parsedTodos : [...initialMockTodos]
  } catch {
    return [...initialMockTodos]
  }
}

function writeMockTodos(todos) {
  window.localStorage.setItem(MOCK_TODOS_STORAGE_KEY, JSON.stringify(todos))
}

export async function fetchTodos() {
  if (shouldUseMockApi) {
    return readMockTodos()
  }

  const response = await fetch('/api/to-dos')

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, 'Failed to load todos.'))
  }

  return response.json()
}

export async function createTodo(title) {
  if (shouldUseMockApi) {
    const nextTodo = {
      id: `mock-${Date.now()}`,
      title,
      completed: false,
    }
    const todos = [nextTodo, ...readMockTodos()]

    writeMockTodos(todos)
    return nextTodo
  }

  const response = await fetch('/api/to-dos', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
  })

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, 'Failed to create todo.'))
  }

  return response.json()
}

export async function deleteTodo(todoId) {
  if (shouldUseMockApi) {
    const todos = readMockTodos().filter((todo) => String(todo.id) !== String(todoId))

    writeMockTodos(todos)
    return
  }

  const response = await fetch(`/api/to-dos/${todoId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, 'Failed to delete todo.'))
  }
}

export async function toggleTodoComplete(todoId) {
  if (shouldUseMockApi) {
    const todos = readMockTodos()
    const updatedTodos = todos.map((todo) =>
      String(todo.id) === String(todoId)
        ? { ...todo, completed: !todo.completed }
        : todo,
    )
    const updatedTodo = updatedTodos.find((todo) => String(todo.id) === String(todoId))

    writeMockTodos(updatedTodos)

    if (!updatedTodo) {
      throw new Error('Todo not found.')
    }

    return updatedTodo
  }

  const response = await fetch(`/api/to-dos/${todoId}/complete`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, 'Failed to update todo.'))
  }

  return response.json()
}