import { useEffect, useState } from 'react'

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

function ContactList({ contacts = [], onContactsChange }) {
  const [items, setItems] = useState(contacts)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let isCancelled = false

    fetch('/api/contacts')
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await getErrorMessage(response, 'Failed to load contacts.'))
        }

        return response.json()
      })
      .then((loadedContacts) => {
        if (!isCancelled) {
          const nextContacts = Array.isArray(loadedContacts) ? loadedContacts : []

          setItems(nextContacts)
          onContactsChange?.(nextContacts)
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
  }, [onContactsChange])

  const displayedContacts = contacts.length > 0 || items.length === 0 ? contacts : items

  if (error) {
    return <p className="status error">{error}</p>
  }

  if (isLoading) {
    return <p className="status">로딩 중...</p>
  }

  if (displayedContacts.length === 0) {
    return <p className="status">등록된 연락처가 없습니다.</p>
  }

  return (
    <ul className="todo-list">
      {displayedContacts.map((contact) => (
        <li key={contact.id} className="todo-item">
          <span>{contact.name ?? contact.email ?? '이름 없음'}</span>
        </li>
      ))}
    </ul>
  )
}

export default ContactList