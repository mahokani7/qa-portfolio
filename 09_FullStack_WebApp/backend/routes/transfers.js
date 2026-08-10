import { Router } from 'express'
import mongoose from 'mongoose'
import Account from '../models/Account.js'

const router = Router()

router.post('/transfer', async (request, response) => {
  const fromAccountId = request.body?.fromAccountId?.trim()
  const toAccountId = request.body?.toAccountId?.trim()
  const amount = Number(request.body?.amount)

  if (!fromAccountId || !toAccountId) {
    response.status(400).json({ message: 'Both source and destination accounts are required.' })
    return
  }

  if (fromAccountId === toAccountId) {
    response.status(400).json({ message: 'Source and destination accounts must differ.' })
    return
  }

  if (!Number.isFinite(amount) || amount <= 0) {
    response.status(400).json({ message: 'A positive transfer amount is required.' })
    return
  }

  const session = await mongoose.startSession()

  try {
    let transferResult

    await session.withTransaction(async () => {
      const fromAccount = await Account.findById(fromAccountId).session(session)
      const toAccount = await Account.findById(toAccountId).session(session)

      if (!fromAccount || !toAccount) {
        throw new Error('ACCOUNT_NOT_FOUND')
      }

      if (fromAccount.balance < amount) {
        throw new Error('INSUFFICIENT_FUNDS')
      }

      fromAccount.balance -= amount
      toAccount.balance += amount

      await fromAccount.save({ session })
      await toAccount.save({ session })

      transferResult = {
        fromAccount,
        toAccount,
        amount,
      }
    })

    response.status(200).json({
      message: 'Transfer completed successfully.',
      amount: transferResult.amount,
      fromAccount: transferResult.fromAccount,
      toAccount: transferResult.toAccount,
    })
  } catch (error) {
    if (error.message === 'ACCOUNT_NOT_FOUND') {
      response.status(404).json({ message: 'One or both accounts were not found.' })
      return
    }

    if (error.message === 'INSUFFICIENT_FUNDS') {
      response.status(400).json({ message: 'The source account does not have enough funds.' })
      return
    }

    response.status(500).json({ message: 'Failed to complete the transfer atomically.' })
  } finally {
    await session.endSession()
  }
})

export default router