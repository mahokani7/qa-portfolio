import { useState } from 'react'
import './LoginForm.css'

function RegisterForm({ error = '', isSubmitting = false, onSubmit, successMessage = '' }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  function handleSubmit(event) {
    event.preventDefault()

    onSubmit?.(
      {
        name,
        email,
        password,
        confirmPassword,
      },
      event,
    )
  }

  return (
    <main className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <a className="login-back-link" href="/login">
          로그인 화면으로 돌아가기
        </a>

        <div className="login-field">
          <label htmlFor="register-name">사용자 이름</label>
          <input
            id="register-name"
            name="name"
            type="text"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="username"
          />
        </div>

        <div className="login-field">
          <label htmlFor="register-email">이메일</label>
          <input
            id="register-email"
            name="email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
          />
        </div>

        <div className="login-field">
          <label htmlFor="register-password">비밀번호</label>
          <input
            id="register-password"
            name="password"
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
          />
        </div>

        <div className="login-field">
          <label htmlFor="register-confirm-password">비밀번호 확인</label>
          <input
            id="register-confirm-password"
            name="confirmPassword"
            type="password"
            required
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
          />
        </div>

        <p className="login-help">
          비밀번호는 8자 이상이며 대문자, 소문자, 숫자, 특수문자를 포함해야 합니다.
        </p>

        {error ? <p className="login-status login-status-error">{error}</p> : null}
        {successMessage ? <p className="login-status login-status-success">{successMessage}</p> : null}

        <button className="login-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? '가입 중...' : '회원가입'}
        </button>
      </form>
    </main>
  )
}

export default RegisterForm