import 'dotenv/config'
import express from 'express'
import http from 'node:http'
import mongoose from 'mongoose'
import contactsRouter from './routes/contacts.js'
import { initializeSocket } from './socket.js'
import todosRouter from './routes/todos.js'
import transfersRouter from './routes/transfers.js'
import usersRouter from './routes/users.js'

const app = express()
const server = http.createServer(app)
const port = process.env.PORT || 3001
const mongoUri = process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/todo-app'

app.use(express.json())

app.use('/api', contactsRouter)
app.use('/api', todosRouter)
app.use('/api', transfersRouter)
app.use('/api', usersRouter)

initializeSocket(server)

async function startServer() {
  try {
    await mongoose.connect(mongoUri)
    server.listen(port, () => {
      console.log(`Todo API listening on http://localhost:${port}`)
    })
  } catch (error) {
    console.error('Failed to connect to MongoDB.', error)
    process.exit(1)
  }
}

startServer()