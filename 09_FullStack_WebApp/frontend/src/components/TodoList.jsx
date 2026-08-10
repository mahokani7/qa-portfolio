import { useEffect, useState } from 'react'
import { fetchTodos, toggleTodoComplete } from '../lib/todoApi.js'

function TodoList({ todos, onDelete, onTodosChange }) {
  const [items, setItems] = useState(todos)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [exitingTodoIds, setExitingTodoIds] = useState([])

  useEffect(() => {
    let isCancelled = false

    fetchTodos()
      .then((loadedTodos) => {
        if (!isCancelled) {
          setItems(loadedTodos)
          onTodosChange?.(loadedTodos)
        }
      })
      .catch((loadError) => {
        if (!isCancelled) {
          setError(loadError.message)
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [onTodosChange])

  const displayedTodos = todos.length > 0 || items.length === 0 ? todos : items

  async function handleToggle(todoId) {
    try {
      setError('')

      const currentTodo = displayedTodos.find((todo) => todo.id === todoId)

      if (!currentTodo || currentTodo.completed || exitingTodoIds.includes(todoId)) {
        return
      }

      const updatedTodo = await toggleTodoComplete(todoId)
      const nextTodos = displayedTodos.map((todo) =>
        todo.id === updatedTodo.id ? updatedTodo : todo,
      )

      setItems(nextTodos)
      onTodosChange?.(nextTodos)

      if (updatedTodo.completed) {
        setExitingTodoIds((currentIds) => [...currentIds, todoId])

        setTimeout(async () => {
          const filteredTodos = nextTodos.filter((todo) => todo.id !== todoId)

          setItems(filteredTodos)
          setExitingTodoIds((currentIds) => currentIds.filter((id) => id !== todoId))
          onTodosChange?.(filteredTodos)
          await onDelete?.(todoId, { skipLocalUpdate: true })
        }, 1000)
      }
    } catch (toggleError) {
      setError(toggleError.message)
    }
  }

  function handleDelete(todoId) {
    setItems((currentItems) => currentItems.filter((todo) => todo.id !== todoId))
    onDelete?.(todoId)
  }

  if (error) {
    return <p className="status error">{error}</p>
  }

  if (isLoading) {
    return <p className="status">불러오는 중...</p>
  }

  if (displayedTodos.length === 0) {
    return <p className="status">등록된 할 일이 없습니다.</p>
  }

  return (
    <ul className="todo-list">
      {displayedTodos.map((todo) => (
        <li
          key={todo.id}
          className={`todo-item${exitingTodoIds.includes(todo.id) ? ' is-exiting' : ''}`}
        >
          <label className="todo-check">
            <input
              type="checkbox"
              checked={todo.completed}
              disabled={exitingTodoIds.includes(todo.id)}
              onChange={() => handleToggle(todo.id)}
            />
            <span className={todo.completed ? 'completed' : ''}>{todo.title}</span>
          </label>
          {onDelete ? (
            <button
              type="button"
              className="ghost-button"
              disabled={exitingTodoIds.includes(todo.id)}
              onClick={() => handleDelete(todo.id)}
            >
              삭제
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

export default TodoList