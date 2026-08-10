import { useState } from 'react'
import LoginForm from './LoginForm.jsx'
import { login } from '../lib/authApi.js'
import { setAuthSession } from '../lib/authSession.js'

function LoginPage() {
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState(() => {
    if (new URLSearchParams(window.location.search).get('registered') === '1') {
      return '회원가입이 완료되었습니다. 로그인하세요.'
    }

    return ''
  })

  async function handleSubmit(credentials) {
    try {
      setIsSubmitting(true)
      setError('')

      const result = await login(credentials)
      setAuthSession(result)
      setSuccessMessage('로그인되었습니다. 홈으로 이동합니다.')

      window.location.replace('/')
    } catch (submitError) {
      setSuccessMessage('')
      setError(submitError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <LoginForm
      error={error}
      isSubmitting={isSubmitting}
      onSubmit={handleSubmit}
      successMessage={successMessage}
    />
  )
}

export default LoginPage