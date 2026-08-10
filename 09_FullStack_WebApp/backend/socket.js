import { Server } from 'socket.io'

let ioInstance

export function initializeSocket(server) {
  ioInstance = new Server(server, {
    cors: {
      origin: '*',
    },
  })

  return ioInstance
}

export function getSocket() {
  if (!ioInstance) {
    throw new Error('Socket.io has not been initialized yet.')
  }

  return ioInstance
}