import React, { useState, useEffect } from 'react'
import { useChatStore, WorkflowPlan } from '../store/chatStore'
import { updatePlan } from '../services/api'
import { ArrowUp, ArrowDown, Plus, Trash2, Edit2, Save, X } from 'lucide-react'

interface PlanEditorProps {
  workflowId: string
  initialPlan: WorkflowPlan
  onClose: () => void
}

export function PlanEditor({ workflowId, initialPlan, onClose }: PlanEditorProps) {
  const [planText, setPlanText] = useState(initialPlan.plan)
  const [steps, setSteps] = useState<string[]>(initialPlan.steps)
  const [isEditingRaw, setIsEditingRaw] = useState(false)
  const [editingStepIndex, setEditingStepIndex] = useState<number | null>(null)
  const [editingStepText, setEditingStepText] = useState('')
  const [rawText, setRawText] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  
  const currentSession = useChatStore((state) => state.currentSession)

  // Initialize raw text when switching to raw mode
  useEffect(() => {
    if (isEditingRaw) {
      setRawText(JSON.stringify({ plan: planText, steps }, null, 2))
    }
  }, [isEditingRaw, planText, steps])

  const handleAddStep = () => {
    setSteps([...steps, 'Новый шаг'])
  }

  const handleDeleteStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index))
  }

  const handleStartEditStep = (index: number) => {
    setEditingStepIndex(index)
    setEditingStepText(steps[index])
  }

  const handleSaveStep = () => {
    if (editingStepIndex !== null) {
      const newSteps = [...steps]
      newSteps[editingStepIndex] = editingStepText
      setSteps(newSteps)
      setEditingStepIndex(null)
      setEditingStepText('')
    }
  }

  const handleCancelEditStep = () => {
    setEditingStepIndex(null)
    setEditingStepText('')
  }

  const handleMoveStep = (index: number, direction: 'up' | 'down') => {
    const newSteps = [...steps]
    if (direction === 'up' && index > 0) {
      [newSteps[index - 1], newSteps[index]] = [newSteps[index], newSteps[index - 1]]
      setSteps(newSteps)
    } else if (direction === 'down' && index < newSteps.length - 1) {
      [newSteps[index], newSteps[index + 1]] = [newSteps[index + 1], newSteps[index]]
      setSteps(newSteps)
    }
  }

  const handleSaveRaw = () => {
    try {
      const parsed = JSON.parse(rawText)
      if (parsed.plan && Array.isArray(parsed.steps)) {
        setPlanText(parsed.plan)
        setSteps(parsed.steps)
        setIsEditingRaw(false)
      } else {
        alert('Неверный формат. Ожидается объект с полями "plan" (строка) и "steps" (массив строк)')
      }
    } catch (e) {
      alert('Ошибка парсинга JSON: ' + (e instanceof Error ? e.message : String(e)))
    }
  }

  const handleSave = async () => {
    if (!currentSession || !initialPlan.confirmationId) {
      alert('Ошибка: отсутствует session ID или confirmation ID')
      return
    }

    setIsSaving(true)
    try {
      await updatePlan(currentSession, initialPlan.confirmationId, {
        plan: planText,
        steps: steps,
      })
      onClose()
    } catch (error) {
      console.error('Error updating plan:', error)
      alert('Ошибка при сохранении плана: ' + (error instanceof Error ? error.message : String(error)))
    } finally {
      setIsSaving(false)
    }
  }

  if (isEditingRaw) {
    return (
      <div style={{ 
        padding: '20px', 
        border: '2px solid #007bff', 
        borderRadius: '8px', 
        margin: '10px',
        background: '#f8f9fa'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h3 style={{ margin: 0 }}>Редактирование плана (JSON)</h3>
          <button
            onClick={() => setIsEditingRaw(false)}
            style={{
              padding: '5px 10px',
              background: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            <X size={16} />
          </button>
        </div>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          style={{
            width: '100%',
            minHeight: '300px',
            fontFamily: 'monospace',
            fontSize: '12px',
            padding: '10px',
            border: '1px solid #ccc',
            borderRadius: '4px'
          }}
        />
        <div style={{ marginTop: '10px', display: 'flex', gap: '10px' }}>
          <button
            onClick={handleSaveRaw}
            style={{
              padding: '8px 16px',
              background: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Применить JSON
          </button>
          <button
            onClick={() => setIsEditingRaw(false)}
            style={{
              padding: '8px 16px',
              background: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Отмена
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ 
      padding: '20px', 
      border: '2px solid #007bff', 
      borderRadius: '8px', 
      margin: '10px',
      background: '#f8f9fa'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h3 style={{ margin: 0 }}>Редактирование плана</h3>
        <button
          onClick={() => setIsEditingRaw(true)}
          style={{
            padding: '5px 10px',
            background: '#17a2b8',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px'
          }}
        >
          Редактировать JSON
        </button>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Текст плана:
        </label>
        <textarea
          value={planText}
          onChange={(e) => setPlanText(e.target.value)}
          style={{
            width: '100%',
            minHeight: '100px',
            padding: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <label style={{ fontWeight: 'bold' }}>Шаги:</label>
          <button
            onClick={handleAddStep}
            style={{
              padding: '5px 10px',
              background: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '12px'
            }}
          >
            <Plus size={14} />
            Добавить шаг
          </button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {steps.map((step, index) => (
            <div
              key={index}
              style={{
                padding: '10px',
                border: '1px solid #ccc',
                borderRadius: '4px',
                background: 'white',
                display: 'flex',
                alignItems: 'center',
                gap: '10px'
              }}
            >
              <span style={{ fontWeight: 'bold', minWidth: '30px' }}>{index + 1}.</span>
              {editingStepIndex === index ? (
                <>
                  <input
                    type="text"
                    value={editingStepText}
                    onChange={(e) => setEditingStepText(e.target.value)}
                    style={{
                      flex: 1,
                      padding: '5px',
                      border: '1px solid #007bff',
                      borderRadius: '4px'
                    }}
                    autoFocus
                  />
                  <button
                    onClick={handleSaveStep}
                    style={{
                      padding: '5px 10px',
                      background: '#28a745',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    <Save size={14} />
                  </button>
                  <button
                    onClick={handleCancelEditStep}
                    style={{
                      padding: '5px 10px',
                      background: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    <X size={14} />
                  </button>
                </>
              ) : (
                <>
                  <span style={{ flex: 1 }}>{step}</span>
                  <button
                    onClick={() => handleStartEditStep(index)}
                    style={{
                      padding: '5px 10px',
                      background: '#17a2b8',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                    title="Редактировать"
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => handleMoveStep(index, 'up')}
                    disabled={index === 0}
                    style={{
                      padding: '5px 10px',
                      background: index === 0 ? '#ccc' : '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: index === 0 ? 'not-allowed' : 'pointer'
                    }}
                    title="Вверх"
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    onClick={() => handleMoveStep(index, 'down')}
                    disabled={index === steps.length - 1}
                    style={{
                      padding: '5px 10px',
                      background: index === steps.length - 1 ? '#ccc' : '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: index === steps.length - 1 ? 'not-allowed' : 'pointer'
                    }}
                    title="Вниз"
                  >
                    <ArrowDown size={14} />
                  </button>
                  <button
                    onClick={() => handleDeleteStep(index)}
                    style={{
                      padding: '5px 10px',
                      background: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                    title="Удалить"
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
        <button
          onClick={handleSave}
          disabled={isSaving}
          style={{
            padding: '8px 16px',
            background: isSaving ? '#ccc' : '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isSaving ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '5px'
          }}
        >
          <Save size={16} />
          {isSaving ? 'Сохранение...' : 'Сохранить'}
        </button>
        <button
          onClick={onClose}
          style={{
            padding: '8px 16px',
            background: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Отмена
        </button>
      </div>
    </div>
  )
}



