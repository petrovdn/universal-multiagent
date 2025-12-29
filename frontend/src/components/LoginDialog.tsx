import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { login } from '../services/api'

interface LoginDialogProps {
  onLoginSuccess: (sessionId: string, username: string) => void
}

export function LoginDialog({ onLoginSuccess }: LoginDialogProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      console.log('Attempting login with username:', username)
      const result = await login(username, password)
      console.log('Login successful:', result)
      onLoginSuccess(result.session_id, result.username)
    } catch (err: any) {
      console.error('Login error details:', err)
      const errorMessage = err.message || err.response?.data?.detail || 'Ошибка входа'
      console.error('Error message:', errorMessage)
      setError(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-dialog-overlay">
      <div className="login-dialog">
        <h2 className="login-dialog-title">
          Вход в систему
        </h2>
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label 
              htmlFor="username" 
              className="login-label"
            >
              Имя пользователя
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="login-input"
              placeholder="Введите имя пользователя"
              disabled={isLoading}
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="login-field">
            <label 
              htmlFor="password" 
              className="login-label"
            >
              Пароль
            </label>
            <div className="login-password-wrapper">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="login-input login-password-input"
                placeholder="Введите пароль"
                disabled={isLoading}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="login-password-toggle"
                tabIndex={-1}
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="login-button"
          >
            {isLoading ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

