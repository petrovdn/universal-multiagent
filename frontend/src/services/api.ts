import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 seconds timeout
  withCredentials: true, // Send cookies with requests
})

// Add request interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      error.message = 'Превышено время ожидания ответа от сервера'
    } else if (error.response) {
      // Server responded with error status
      const status = error.response.status
      if (status === 404) {
        error.message = 'Сессия не найдена'
      } else if (status === 500) {
        error.message = error.response.data?.detail || 'Внутренняя ошибка сервера'
      } else if (status === 400) {
        error.message = error.response.data?.detail || 'Неверный запрос'
      }
    } else if (error.request) {
      // Request was made but no response received
      error.message = 'Не удалось подключиться к серверу. Проверьте, что сервер запущен.'
    }
    return Promise.reject(error)
  }
)

export interface Model {
  id: string
  name: string
  provider: 'anthropic' | 'openai'
  supports_reasoning: boolean
  reasoning_type?: 'extended_thinking' | 'native' | null
  default: boolean
}

export interface SendMessageRequest {
  message: string
  session_id?: string
  execution_mode?: 'instant' | 'approval'
}

export interface SendMessageResponse {
  session_id: string
  result: any
}

export const sendMessage = async (
  request: SendMessageRequest
): Promise<SendMessageResponse> => {
  const response = await api.post<SendMessageResponse>('/chat', request)
  return response.data
}

export const getHistory = async (sessionId: string) => {
  const response = await api.get(`/chat/history/${sessionId}`)
  return response.data
}

export const updateSettings = async (settings: {
  session_id: string
  execution_mode?: 'instant' | 'approval'
  model_name?: string
}) => {
  const response = await api.post('/settings', settings)
  return response.data
}

export const approvePlan = async (sessionId: string, confirmationId: string) => {
  const response = await api.post('/plan/approve', {
    session_id: sessionId,
    confirmation_id: confirmationId,
  })
  return response.data
}

export const rejectPlan = async (sessionId: string, confirmationId: string) => {
  const response = await api.post('/plan/reject', {
    session_id: sessionId,
    confirmation_id: confirmationId,
  })
  return response.data
}

export const healthCheck = async () => {
  const response = await api.get('/health')
  return response.data
}

export const createSession = async (executionMode: 'instant' | 'approval' = 'instant', modelName?: string) => {
  const request: any = { execution_mode: executionMode }
  if (modelName) {
    request.model_name = modelName
  }
  const response = await api.post('/session/create', request)
  return response.data
}

// Integration APIs
export const getIntegrationsStatus = async () => {
  const response = await api.get('/integrations/status')
  return response.data
}

export const enableGoogleCalendar = async () => {
  const response = await api.post('/integrations/google-calendar/enable')
  return response.data
}

export const disableGoogleCalendar = async () => {
  const response = await api.post('/integrations/google-calendar/disable')
  return response.data
}

export const getGoogleCalendarStatus = async () => {
  const response = await api.get('/integrations/google-calendar/status')
  return response.data
}

// Gmail Integration APIs
export const enableGmail = async () => {
  const response = await api.post('/integrations/gmail/enable')
  return response.data
}

export const disableGmail = async () => {
  const response = await api.post('/integrations/gmail/disable')
  return response.data
}

export const getGmailStatus = async () => {
  const response = await api.get('/integrations/gmail/status')
  return response.data
}

// Google Sheets Integration APIs
export const enableGoogleSheets = async () => {
  const response = await api.post('/integrations/google-sheets/enable')
  return response.data
}

export const disableGoogleSheets = async () => {
  const response = await api.post('/integrations/google-sheets/disable')
  return response.data
}

export const getGoogleSheetsStatus = async () => {
  const response = await api.get('/integrations/google-sheets/status')
  return response.data
}

// Google Workspace Integration APIs
export const enableGoogleWorkspace = async () => {
  const response = await api.post('/integrations/google-workspace/enable')
  return response.data
}

export const disableGoogleWorkspace = async () => {
  const response = await api.post('/integrations/google-workspace/disable')
  return response.data
}

export const getGoogleWorkspaceStatus = async () => {
  const response = await api.get('/integrations/google-workspace/status')
  return response.data
}

export const listWorkspaceFolders = async () => {
  const response = await api.get('/integrations/google-workspace/folders')
  return response.data
}

export const setWorkspaceFolder = async (folderId: string, folderName?: string) => {
  const params = new URLSearchParams({ folder_id: folderId })
  if (folderName) {
    params.append('folder_name', folderName)
  }
  const response = await api.post(`/integrations/google-workspace/set-folder?${params.toString()}`)
  return response.data
}

export const getCurrentWorkspaceFolder = async () => {
  const response = await api.get('/integrations/google-workspace/current-folder')
  return response.data
}

export const createWorkspaceFolder = async (folderName: string, parentFolderId?: string) => {
  const params = new URLSearchParams({ folder_name: folderName })
  if (parentFolderId) {
    params.append('parent_folder_id', parentFolderId)
  }
  const response = await api.post(`/integrations/google-workspace/create-folder?${params.toString()}`)
  return response.data
}

// Model APIs
export const fetchModels = async (): Promise<{ models: Model[] }> => {
  const response = await api.get<{ models: Model[] }>('/models')
  return response.data
}

export const setSessionModel = async (sessionId: string, modelId: string) => {
  const response = await api.post('/session/model', {
    session_id: sessionId,
    model_name: modelId,
  })
  return response.data
}

