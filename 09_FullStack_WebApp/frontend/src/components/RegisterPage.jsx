import { useState } from 'react'
import RegisterForm from './RegisterForm.jsx'
import { register } from '../lib/authApi.js'

function RegisterPage() {
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  async function handleSubmit(credentials) {
    if (credentials.password !== credentials.confirmPassword) {
      setSuccessMessage('')
      setError('비밀번호와 비밀번호 확인이 일치하지 않습니다.')
      return
    }

    try {
      setIsSubmitting(true)
      setError('')

      await register(credentials)
      setSuccessMessage('회원가입이 완료되었습니다. 로그인 화면으로 이동합니다.')
      window.location.replace('/login?registered=1')
    } catch (submitError) {
      setSuccessMessage('')
      setError(submitError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <RegisterForm
      error={error}
      isSubmitting={isSubmitting}
      onSubmit={handleSubmit}
      successMessage={successMessage}
    />
  )
}

export default RegisterPage