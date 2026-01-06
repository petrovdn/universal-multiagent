import { useState } from 'react'
import { useChatStore } from '../store/chatStore'
import { resolveUserAssistance } from '../services/api'

interface UserAssistanceDialogProps {
  assistance_id: string
  question: string
  options: Array<{ id: string; label: string; description?: string; data?: any }>
  context?: any
}

export function UserAssistanceDialog({
  assistance_id,
  question,
  options,
  context
}: UserAssistanceDialogProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const { currentSession, clearUserAssistanceRequest } = useChatStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!selectedOption) {
      setError('Пожалуйста, выберите вариант')
      return
    }

    if (!currentSession) {
      setError('Сессия не найдена')
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      // Find the selected option to get its label or ID
      const option = options.find(opt => opt.id === selectedOption) || 
                     options.find(opt => opt.label === selectedOption)
      
      const userResponse = option?.id || selectedOption
      
      const result = await resolveUserAssistance(currentSession, assistance_id, userResponse)
      
      // Clear the assistance request from store
      clearUserAssistanceRequest()
    } catch (err: any) {
      console.error('Error resolving user assistance:', err)
      setError(err.message || 'Ошибка при отправке выбора')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleOptionClick = (optionId: string) => {
    setSelectedOption(optionId)
    setError('')
  }

  const handleTextInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.trim()
    setSelectedOption(value)
    setError('')
  }

  return (
    <div className="user-assistance-overlay">
      <div className="user-assistance-dialog">
        <h2 className="user-assistance-title">
          Требуется ваш выбор
        </h2>
        
        <div className="user-assistance-question">
          {question}
        </div>

        <form onSubmit={handleSubmit} className="user-assistance-form">
          <div className="user-assistance-options">
            {options.map((option) => (
              <div
                key={option.id}
                className={`user-assistance-option ${
                  selectedOption === option.id ? 'selected' : ''
                }`}
                onClick={() => handleOptionClick(option.id)}
              >
                <div className="user-assistance-option-number">
                  {option.id}
                </div>
                <div className="user-assistance-option-content">
                  <div className="user-assistance-option-label">
                    {option.label}
                  </div>
                  {option.description && (
                    <div className="user-assistance-option-description">
                      {option.description}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="user-assistance-input-section">
            <label htmlFor="user-response" className="user-assistance-input-label">
              Или введите номер (1-{options.length}), название или "первый"/"второй":
            </label>
            <input
              id="user-response"
              type="text"
              className="user-assistance-input"
              placeholder="Например: 1, первый, или название файла"
              value={selectedOption || ''}
              onChange={handleTextInput}
              disabled={isSubmitting}
            />
          </div>

          {error && (
            <div className="user-assistance-error">
              {error}
            </div>
          )}

          <div className="user-assistance-actions">
            <button
              type="submit"
              className="user-assistance-submit"
              disabled={!selectedOption || isSubmitting}
            >
              {isSubmitting ? 'Отправка...' : 'Выбрать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

