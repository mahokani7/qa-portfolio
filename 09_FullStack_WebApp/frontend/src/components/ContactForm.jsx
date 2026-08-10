import { useState } from 'react'

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

function ContactForm({ onContactCreated }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()

    try {
      setIsSubmitting(true)
      setError('')

      const response = await fetch('/api/contacts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: name.trim(), email: email.trim() }),
      })

      if (!response.ok) {
        throw new Error(await getErrorMessage(response, 'Failed to create contact.'))
      }

      const createdContact = await response.json()
      onContactCreated?.(createdContact)
      setName('')
      setEmail('')
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="todo-form" onSubmit={handleSubmit}>
      <label className="input-label" htmlFor="contact-name">
        이름
      </label>
      <div className="input-row">
        <input
          id="contact-name"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="예: 홍길동"
        />
      </div>

      <label className="input-label" htmlFor="contact-email">
        이메일
      </label>
      <div className="input-row">
        <input
          id="contact-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="example@email.com"
        />
      </div>

      {error ? <p className="status error">{error}</p> : null}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? '저장 중...' : '연락처 추가'}
      </button>
    </form>
  )
}

export default ContactForm