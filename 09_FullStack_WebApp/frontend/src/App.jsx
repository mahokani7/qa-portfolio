import { useEffect, useState } from 'react'
import { io } from 'socket.io-client'
import './App.css'
import TodoList from './components/TodoList.jsx'
import { clearAuthSession, getAuthSession } from './lib/authSession.js'
import { createTodo, deleteTodo, shouldUseMockApi } from './lib/todoApi.js'

function App() {
  const [authSession, setAuthSession] = useState(() => getAuthSession())
  const [todos, setTodos] = useState([])
  const [title, setTitle] = useState('')
  const [memo, setMemo] = useState('')
  const [showMemo, setShowMemo] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  function prependTodo(nextTodo) {
    setTodos((currentTodos) => {
      if (currentTodos.some((currentTodo) => currentTodo.id === nextTodo.id)) {
        return currentTodos
      }

      return [nextTodo, ...currentTodos]
    })
  }

  function handleLogout() {
    clearAuthSession()
    setAuthSession(null)
    window.location.replace('/login')
  }

  useEffect(() => {
    if (shouldUseMockApi) {
      return undefined
    }

    const socket = io()

    socket.on('todo:created', (todo) => {
      prependTodo(todo)
    })

    return () => {
      socket.disconnect()
    }
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()

    const trimmedTitle = title.trim()

    if (!trimmedTitle) {
      setError('할 일 제목을 입력하세요.')
      return
    }

    try {
      setIsSubmitting(true)
      setError('')

      const todo = await createTodo(trimmedTitle)
      prependTodo(todo)
      setTitle('')
      setMemo('')
      setShowMemo(false)
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(todoId, options = {}) {
    try {
      setError('')

      await deleteTodo(todoId)

      if (!options.skipLocalUpdate) {
        setTodos((currentTodos) => currentTodos.filter((todo) => todo.id !== todoId))
      }
    } catch (deleteError) {
      setError(deleteError.message)
    }
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <p className="eyebrow">React + Express</p>
        <h1>Todo workspace</h1>
        <p className="hero-copy">
          Vite 개발 서버는 <code>/api</code> 요청을 Express 백엔드로 프록시합니다.
        </p>
        {authSession?.user ? (
          <div className="auth-summary">
            <p className="hero-copy">
              로그인 사용자: <strong>{authSession.user.name}</strong>
            </p>
            <button className="hero-link-button" type="button" onClick={handleLogout}>
              로그아웃
            </button>
          </div>
        ) : (
          <p className="hero-copy">
            <a className="hero-link" href="/login">
              로그인 페이지로 이동
            </a>
          </p>
        )}
      </section>

      <section className="todo-panel">
        <form className="todo-form" onSubmit={handleSubmit}>
          <label className="input-label" htmlFor="todo-title">
            새 할 일
          </label>
          <div className="input-row">
            <input
              id="todo-title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="예: 프록시 동작 확인하기"
            />
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? '추가 중...' : '추가'}
            </button>
          </div>

          <label className="memo-toggle">
            <input
              type="checkbox"
              checked={showMemo}
              onChange={(event) => {
                const nextShowMemo = event.target.checked

                setShowMemo(nextShowMemo)

                if (!nextShowMemo) {
                  setMemo('')
                }
              }}
            />
            <span>메모 추가</span>
          </label>

          {showMemo ? (
            <div className="memo-field">
              <label className="input-label" htmlFor="todo-memo">
                메모
              </label>
              <textarea
                id="todo-memo"
                value={memo}
                onChange={(event) => setMemo(event.target.value)}
                placeholder="필요한 메모를 입력하세요"
                rows="4"
              />
            </div>
          ) : null}
        </form>

        {error ? <p className="status error">{error}</p> : null}
        <TodoList
          todos={todos}
          onDelete={handleDelete}
          onTodosChange={setTodos}
        />
      </section>
    </main>
  )
}

export default App
