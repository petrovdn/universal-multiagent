import React, { useState } from 'react'
import { Send } from 'lucide-react'
import { QuestionMessageData } from '../store/chatStore'
import { wsClient } from '../services/websocket'

interface QuestionFormProps {
  question: QuestionMessageData
  workflowId: string
  onAnswer?: (questionId: string, answers: Record<string, string | string[]>) => void
}

export function QuestionForm({ question, workflowId, onAnswer }: QuestionFormProps) {
  const [answers, setAnswers] = useState<Record<string, string | string[]>>(() => {
    // Инициализируем из сохраненных значений, если есть
    const initial: Record<string, string | string[]> = {}
    question.items.forEach(item => {
      if (item.value !== undefined) {
        initial[item.id] = item.value
      } else if (item.type === 'checkbox') {
        initial[item.id] = []
      } else {
        initial[item.id] = ''
      }
    })
    return initial
  })

  const handleRadioChange = (itemId: string, value: string) => {
    setAnswers(prev => ({ ...prev, [itemId]: value }))
  }

  const handleCheckboxChange = (itemId: string, option: string, checked: boolean) => {
    setAnswers(prev => {
      const current = (prev[itemId] as string[]) || []
      if (checked) {
        return { ...prev, [itemId]: [...current, option] }
      } else {
        return { ...prev, [itemId]: current.filter(v => v !== option) }
      }
    })
  }

  const handleTextChange = (itemId: string, value: string) => {
    setAnswers(prev => ({ ...prev, [itemId]: value }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Валидация
    const isValid = question.items.every(item => {
      const answer = answers[item.id]
      if (item.type === 'radio' || item.type === 'text') {
        return answer && (answer as string).trim().length > 0
      } else if (item.type === 'checkbox') {
        return Array.isArray(answer) && answer.length > 0
      }
      return true
    })

    if (!isValid) {
      alert('Пожалуйста, ответьте на все вопросы')
      return
    }

    // Отправляем ответы
    if (onAnswer) {
      onAnswer(question.id, answers)
    }

    // Также отправляем через WebSocket (если нужно)
    wsClient.sendMessage(JSON.stringify({
      type: 'question_answer',
      question_id: question.id,
      answers: answers,
    }))
  }

  return (
    <div className="question-form">
      <div className="question-form-text">{question.text}</div>
      
      <form onSubmit={handleSubmit} className="question-form-content">
        {question.items.map((item) => (
          <div key={item.id} className="question-form-item">
            <label className="question-form-item-label">{item.label}</label>
            
            {item.type === 'radio' && item.options && (
              <div className="question-form-options">
                {item.options.map((option) => (
                  <label key={option} className="question-form-radio-option">
                    <input
                      type="radio"
                      name={item.id}
                      value={option}
                      checked={(answers[item.id] as string) === option}
                      onChange={(e) => handleRadioChange(item.id, e.target.value)}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            )}

            {item.type === 'checkbox' && item.options && (
              <div className="question-form-options">
                {item.options.map((option) => {
                  const currentAnswers = (answers[item.id] as string[]) || []
                  return (
                    <label key={option} className="question-form-checkbox-option">
                      <input
                        type="checkbox"
                        checked={currentAnswers.includes(option)}
                        onChange={(e) => handleCheckboxChange(item.id, option, e.target.checked)}
                      />
                      <span>{option}</span>
                    </label>
                  )
                })}
              </div>
            )}

            {item.type === 'text' && (
              <input
                type="text"
                className="question-form-text-input"
                value={(answers[item.id] as string) || ''}
                onChange={(e) => handleTextChange(item.id, e.target.value)}
                placeholder="Введите ответ..."
              />
            )}
          </div>
        ))}

        <button type="submit" className="question-form-submit">
          <Send size={14} />
          Отправить ответы
        </button>
      </form>
    </div>
  )
}

