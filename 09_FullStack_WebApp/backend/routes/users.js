import bcrypt from 'bcrypt'
import { Router } from 'express'
import sendgridMail from '@sendgrid/mail'
import User from '../models/User.js'
import { validatePasswordStrength } from '../utils/passwordStrength.js'

const router = Router()
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const sendgridApiKey = process.env.SENDGRID_API_KEY
const sendgridFromEmail = process.env.SENDGRID_FROM_EMAIL

if (sendgridApiKey) {
  sendgridMail.setApiKey(sendgridApiKey)
}

router.post('/register', async (request, response) => {
  const name = request.body?.name?.trim()
  const email = request.body?.email?.trim().toLowerCase()
  const password = request.body?.password

  if (!name) {
    response.status(400).json({ message: 'A user name is required.' })
    return
  }

  if (!email || !emailPattern.test(email)) {
    response.status(400).json({ message: 'A valid email address is required.' })
    return
  }

  const passwordValidation = validatePasswordStrength(password)

  if (!passwordValidation.isValid) {
    response.status(400).json({ message: passwordValidation.errors[0] })
    return
  }

  try {
    const passwordHash = await bcrypt.hash(password, 10)
    const user = await User.create({
      name,
      email,
      passwordHash,
    })

    response.status(201).json(user)
  } catch (error) {
    if (error?.code === 11000) {
      response.status(409).json({ message: 'A user with that email already exists.' })
      return
    }

    response.status(500).json({ message: 'Failed to register user.' })
  }
})

router.post('/login', async (request, response) => {
  const username = request.body?.username?.trim().toLowerCase()
  const password = request.body?.password

  if (!username || !password) {
    response.status(400).json({ message: 'User name and password are required.' })
    return
  }

  try {
    const user = await User.findOne({
      $or: [
        { email: username },
        { name: username },
      ],
    })

    if (!user?.passwordHash) {
      response.status(401).json({ message: 'Invalid credentials.' })
      return
    }

    const isPasswordValid = await bcrypt.compare(password, user.passwordHash)

    if (!isPasswordValid) {
      response.status(401).json({ message: 'Invalid credentials.' })
      return
    }

    response.json({
      message: '로그인되었습니다.',
      user: user.toJSON(),
    })
  } catch (_error) {
    response.status(500).json({ message: 'Failed to log in.' })
  }
})

router.post('/users', async (request, response) => {
  const name = request.body?.name?.trim()
  const email = request.body?.email?.trim().toLowerCase()

  if (!name) {
    response.status(400).json({ message: 'A user name is required.' })
    return
  }

  if (!email || !emailPattern.test(email)) {
    response.status(400).json({ message: 'A valid email address is required.' })
    return
  }

  if (!sendgridApiKey || !sendgridFromEmail) {
    response.status(500).json({
      message: 'SendGrid is not configured. Set SENDGRID_API_KEY and SENDGRID_FROM_EMAIL.',
    })
    return
  }

  let user

  try {
    user = await User.create({ name, email })
  } catch (error) {
    if (error?.code === 11000) {
      response.status(409).json({ message: 'A user with that email already exists.' })
      return
    }

    response.status(500).json({ message: 'Failed to create user.' })
    return
  }

  try {
    await sendgridMail.send({
      to: user.email,
      from: sendgridFromEmail,
      subject: 'Welcome!',
      text: `Hi ${user.name}, welcome aboard!`,
      html: `<p>Hi ${user.name}, welcome aboard!</p>`,
    })

    response.status(201).json(user)
  } catch (_error) {
    await User.findByIdAndDelete(user.id)
    response.status(502).json({ message: 'Failed to send welcome email.' })
  }
})

export default router