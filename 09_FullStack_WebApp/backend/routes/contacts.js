import { Router } from 'express'
import Contact from '../models/Contact.js'

const router = Router()

router.get('/contacts', async (_request, response) => {
  try {
    const contacts = await Contact.find().sort({ createdAt: -1 })
    response.json(contacts)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to load contacts.' })
  }
})

router.post('/contacts', async (request, response) => {
  const name = request.body?.name?.trim()
  const email = request.body?.email?.trim().toLowerCase()

  if (!name) {
    response.status(400).json({ message: 'A contact name is required.' })
    return
  }

  if (!email) {
    response.status(400).json({ message: 'A contact email is required.' })
    return
  }

  try {
    const contact = await Contact.create({ name, email })
    response.status(201).json(contact)
  } catch (_error) {
    response.status(500).json({ message: 'Failed to create contact.' })
  }
})

export default router