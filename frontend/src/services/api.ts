import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds timeout (increased for user assistance)
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
        // Don't override message for /auth/me endpoint - let it use the detail from server
        const url = error.config?.url || ''
        if (!url.includes('/auth/me')) {
          error.message = 'Сессия не найдена'
        } else {
          error.message = error.response.data?.detail || 'Сессия не найдена'
        }
      } else if (status === 401) {
        error.message = error.response.data?.detail || 'Требуется авторизация'
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
  file_ids?: string[]
}

export interface UploadFileResponse {
  file_id: string
  filename: string
  type: string
  size: number
  data?: string  // base64 encoded image data
  text?: string  // extracted PDF text
  media_type?: string
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

export const resolveUserAssistance = async (
  sessionId: string,
  assistanceId: string,
  userResponse: string
) => {
  // #region agent log
  console.log('[DEBUG] api.ts resolveUserAssistance called', { sessionId, assistanceId, userResponse })
  // #endregion
  
  try {
    // #region agent log
    console.log('[DEBUG] api.ts resolveUserAssistance: making request', { sessionId, assistanceId, userResponse })
    // #endregion
    
    const response = await api.post('/assistance/resolve', {
      session_id: sessionId,
      assistance_id: assistanceId,
      user_response: userResponse,
    })
    
    // #region agent log
    console.log('[DEBUG] api.ts resolveUserAssistance: got response', { status: response.status, data: response.data })
    // #endregion
    
    return response.data
  } catch (err: any) {
    // #region agent log
    console.error('[DEBUG] api.ts resolveUserAssistance: error', { errorMessage: err?.message, errorResponse: err?.response?.data, status: err?.response?.status })
    // #endregion
    throw err
  }
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

export const updatePlan = async (
  sessionId: string,
  confirmationId: string,
  updatedPlan: { plan: string; steps: string[] }
) => {
  const response = await api.post('/plan/update', {
    session_id: sessionId,
    confirmation_id: confirmationId,
    updated_plan: updatedPlan,
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

// 1C OData Integration APIs
export interface OneCConfig {
  odata_base_url: string
  username: string
  password: string
  organization_guid?: string
}

export const saveOneCConfig = async (config: OneCConfig) => {
  const response = await api.post('/integrations/onec/config', config)
  return response.data
}

export const getOneCConfig = async () => {
  const response = await api.get('/integrations/onec/config')
  return response.data
}

export const testOneCConnection = async () => {
  const response = await api.post('/integrations/onec/test')
  return response.data
}

export const getOneCStatus = async () => {
  const response = await api.get('/integrations/onec/status')
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

export const uploadFile = async (file: File, sessionId: string): Promise<UploadFileResponse> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('session_id', sessionId)
  
  const response = await api.post<UploadFileResponse>('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

// Authentication APIs
export const login = async (username: string, password: string) => {
  // #region agent log
  console.log('[api] login called', { username })
  fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:login-start',message:'login called',data:{username},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
  // #endregion
  try {
    console.log('[api] Making login request...')
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:login-before-request',message:'About to make login request',data:{username},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    const response = await api.post('/auth/login', { username, password })
    console.log('[api] login success:', response.data)
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:login-success',message:'login success',data:{username:response.data?.username,sessionId:response.data?.session_id},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    return response.data
  } catch (error: any) {
    // Log error for debugging
    console.error('[api] login error:', error)
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:login-error',message:'login error',data:{error:String(error),status:error?.response?.status,message:error?.message,detail:error?.response?.data?.detail},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    if (error.response?.status === 401) {
      throw new Error(error.response?.data?.detail || 'Неверное имя пользователя или пароль')
    }
    throw error
  }
}

export const logout = async () => {
  const response = await api.post('/auth/logout')
  return response.data
}

export const getCurrentUser = async () => {
  // #region agent log
  console.log('[api] getCurrentUser called')
  fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:getCurrentUser-start',message:'getCurrentUser called',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  try {
    console.log('[api] Making request to /auth/me...')
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:getCurrentUser-before-request',message:'About to make request',data:{url:'/auth/me'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    // Use shorter timeout for auth check (5 seconds)
    const response = await api.get('/auth/me', { timeout: 5000 })
    console.log('[api] getCurrentUser response:', response.data)
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:getCurrentUser-success',message:'getCurrentUser success',data:{username:response.data?.username,status:response.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    return response.data
  } catch (err: any) {
    console.error('[api] getCurrentUser error:', err)
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:getCurrentUser-error',message:'getCurrentUser error',data:{error:String(err),status:err?.response?.status,message:err?.message},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    throw err
  }
}

