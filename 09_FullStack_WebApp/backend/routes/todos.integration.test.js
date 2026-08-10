import express from 'express'
import request from 'supertest'
import { beforeEach, describe, expect, it, jest } from '@jest/globals'

const mockCreate = jest.fn()
const mockFind = jest.fn()
const mockEmit = jest.fn()

jest.unstable_mockModule('../models/Todo.js', () => ({
  default: {
    create: mockCreate,
    find: mockFind,
    findById: jest.fn(),
    countDocuments: jest.fn(),
    findByIdAndDelete: jest.fn(),
  },
}))

jest.unstable_mockModule('../socket.js', () => ({
  getSocket: () => ({
    emit: mockEmit,
  }),
}))

const { default: todosRouter } = await import('./todos.js')

function createTestApp() {
  const app = express()
  app.use(express.json())
  app.use('/api', todosRouter)
  return app
}

describe('/api/to-dos integration', () => {
  beforeEach(() => {
    mockCreate.mockReset()
    mockFind.mockReset()
    mockEmit.mockReset()
  })

  it('returns the todo list from GET /api/to-dos', async () => {
    const todos = [
      { id: 'todo-2', title: 'Second todo', completed: true },
      { id: 'todo-1', title: 'First todo', completed: false },
    ]
    const sort = jest.fn().mockResolvedValue(todos)

    mockFind.mockReturnValue({ sort })

    const response = await request(createTestApp()).get('/api/to-dos')

    expect(response.status).toBe(200)
    expect(response.body).toEqual(todos)
    expect(mockFind).toHaveBeenCalledTimes(1)
    expect(sort).toHaveBeenCalledWith({ createdAt: -1 })
  })

  it('creates and returns a todo from POST /api/to-dos', async () => {
    const createdTodo = {
      id: 'todo-3',
      title: 'Ship integration tests',
      completed: false,
    }

    mockCreate.mockResolvedValue(createdTodo)

    const response = await request(createTestApp())
      .post('/api/to-dos')
      .send({ title: 'Ship integration tests' })

    expect(response.status).toBe(201)
    expect(response.body).toEqual(createdTodo)
    expect(mockCreate).toHaveBeenCalledWith({
      title: 'Ship integration tests',
      completed: false,
    })
    expect(mockEmit).toHaveBeenCalledWith('todo:created', createdTodo)
  })

  it('rejects an empty title from POST /api/to-dos', async () => {
    const response = await request(createTestApp())
      .post('/api/to-dos')
      .send({ title: '   ' })

    expect(response.status).toBe(400)
    expect(response.body).toEqual({ message: 'A todo title is required.' })
    expect(mockCreate).not.toHaveBeenCalled()
    expect(mockEmit).not.toHaveBeenCalled()
  })

  it('rejects a title longer than 100 characters from POST /api/to-dos', async () => {
    const response = await request(createTestApp())
      .post('/api/to-dos')
      .send({ title: 'x'.repeat(101) })

    expect(response.status).toBe(400)
    expect(response.body).toEqual({
      message: 'A todo title must be 100 characters or fewer.',
    })
    expect(mockCreate).not.toHaveBeenCalled()
  })
})