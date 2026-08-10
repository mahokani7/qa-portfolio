import { useState } from 'react'
import ContactForm from './ContactForm.jsx'
import ContactList from './ContactList.jsx'

function ContactDirectory() {
  const [contacts, setContacts] = useState([])

  function handleContactCreated(contact) {
    setContacts((currentContacts) => {
      if (currentContacts.some((currentContact) => currentContact.id === contact.id)) {
        return currentContacts
      }

      return [contact, ...currentContacts]
    })
  }

  return (
    <section className="todo-panel">
      <ContactForm onContactCreated={handleContactCreated} />
      <ContactList contacts={contacts} onContactsChange={setContacts} />
    </section>
  )
}

export default ContactDirectory