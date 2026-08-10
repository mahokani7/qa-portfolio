import { useState } from 'react'
import './LoginForm.css'

function LoginForm({ error = '', isSubmitting = false, onSubmit, successMessage = '' }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(event) {
    event.preventDefault()

    onSubmit?.(
      {
        username,
        password,
      },
      event,
    )
  }

  return (
    <main className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <a className="login-back-link" href="/">
          할 일 화면으로 돌아가기
        </a>

        <p className="login-help">
          아직 계정이 없으면 <a className="login-inline-link" href="/register">회원가입</a> 후 로그인하세요.
        </p>

        <div className="login-field">
          <label htmlFor="login-username">사용자 이름</label>
          <input
            id="login-username"
            name="username"
            type="text"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
          />
        </div>

        <div className="login-field">
          <label htmlFor="login-password">비밀번호</label>
          <input
            id="login-password"
            name="password"
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </div>

        {error ? <p className="login-status login-status-error">{error}</p> : null}
        {successMessage ? <p className="login-status login-status-success">{successMessage}</p> : null}

        <button className="login-submit" type="submit" disabled={isSubmitting}>
          {isSubmitting ? '로그인 중...' : '로그인'}
        </button>
      </form>
    </main>
  )
}

export default LoginForm