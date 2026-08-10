import App from './App.jsx'
import LoginPage from './components/LoginPage.jsx'
import RegisterPage from './components/RegisterPage.jsx'
import { getAuthSession } from './lib/authSession.js'

function AppRouter() {
  const pathname = window.location.pathname
  const authSession = getAuthSession()

  if (authSession && (pathname === '/login' || pathname === '/register')) {
    window.location.replace('/')
    return null
  }

  if (pathname === '/login') {
    return <LoginPage />
  }

  if (pathname === '/register') {
    return <RegisterPage />
  }

  return <App />
}

export default AppRouter