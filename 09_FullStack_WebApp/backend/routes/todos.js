import { Router } from 'express'
import Todo from '../models/Todo.js'
import { getSocket } from '../socket.js'

const router = Router()

async function logIfAllDone() {
  const remainingTodos = await Todo.countDocuments({ completed: false })

  if (remainingTodos === 0) {
    console.log('All done!')
  }
}

async function createTodo(request, response) {
  const title = request.body?.title?.trim()

  if (!title) {
    response.status(400).json({ message: 'A todo title is required.' })
    return
  }

  if (title.length > 100) {
    response.status(400).json({ message: 'A todo title must be 100 characters or fewer.' })
    return
  }

  try {
    const todo = await Todo.create({
      title,
      completed: false,
    })

    getSocket().emit('todo:created', todo)

    response.status(201).json(todo)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to create todo.' })
  }
}

router.get('/health', (_request, response) => {
  response.json({ status: 'ok' })
})

router.get('/todos', async (_request, response) => {
  try {
    const todos = await Todo.find().sort({ createdAt: -1 })
    response.json(todos)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to load todos.' })
  }
})

router.get('/to-dos', async (_request, response) => {
  try {
    const todos = await Todo.find().sort({ createdAt: -1 })
    response.json(todos)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to load todos.' })
  }
})

router.post('/to-dos/:id/complete', async (request, response) => {
  try {
    const todo = await Todo.findById(request.params.id)

    if (!todo) {
      response.status(404).json({ message: 'Todo not found.' })
      return
    }

    todo.completed = !todo.completed
    await todo.save()

    if (todo.completed) {
      await logIfAllDone()
    }

    response.json(todo)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to update todo.' })
  }
})

router.put('/to-dos/:id', async (request, response) => {
  try {
    const todo = await Todo.findById(request.params.id)

    if (!todo) {
      response.status(404).json({ message: 'Todo not found.' })
      return
    }

    if (typeof request.body?.completed !== 'boolean') {
      response.status(400).json({ message: 'A completed flag is required.' })
      return
    }

    todo.completed = request.body.completed
    await todo.save()

    if (todo.completed) {
      await logIfAllDone()
    }

    response.json(todo)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to update todo.' })
  }
})

router.post('/to-dos', createTodo)

router.post('/todos', createTodo)

router.patch('/todos/:id', async (request, response) => {
  try {
    const todo = await Todo.findById(request.params.id)

    if (!todo) {
      response.status(404).json({ message: 'Todo not found.' })
      return
    }

    if (typeof request.body?.title === 'string') {
      const title = request.body.title.trim()

      if (!title) {
        response.status(400).json({ message: 'A todo title is required.' })
        return
      }

      todo.title = title
    }

    if (typeof request.body?.completed === 'boolean') {
      todo.completed = request.body.completed
    }

    await todo.save()
    response.json(todo)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to update todo.' })
  }
})

async function deleteTodo(request, response) {
  try {
    const deletedTodo = await Todo.findByIdAndDelete(request.params.id)

    if (!deletedTodo) {
      response.status(404).json({ message: 'Todo not found.' })
      return
    }

    response.status(204).send()
  } catch (_error) {
    response.status(500).json({ message: 'Failed to delete todo.' })
  }
}

router.delete('/to-dos/:id', deleteTodo)

router.delete('/todos/:id', deleteTodo)

export default router