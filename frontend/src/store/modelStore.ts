import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { fetchModels as apiFetchModels } from '../services/api'

export interface Model {
  id: string
  name: string
  provider: 'anthropic' | 'openai'
  supports_reasoning: boolean
  reasoning_type?: 'extended_thinking' | 'native' | null
  default: boolean
}

interface ModelState {
  models: Model[]
  selectedModel: string | null
  isLoading: boolean
  error: string | null
  setSelectedModel: (modelId: string) => void
  fetchModels: () => Promise<void>
}

export const useModelStore = create<ModelState>()(
  persist(
    (set, get) => ({
      models: [],
      selectedModel: null,
      isLoading: false,
      error: null,
      
      setSelectedModel: (modelId: string) => {
        set({ selectedModel: modelId })
      },
      
      fetchModels: async () => {
        console.log('[ModelStore] Starting to fetch models...')
        set({ isLoading: true, error: null })
        try {
          const result = await apiFetchModels()
          const models: Model[] = result.models || []
          console.log('[ModelStore] Models fetched successfully:', models)
          console.log('[ModelStore] Models count:', models.length)
          
          if (models.length === 0) {
            console.warn('[ModelStore] No models returned from API')
            set({ error: 'Нет доступных моделей. Проверьте, что API ключи установлены на сервере.', isLoading: false, models: [] })
            return
          }
          
          // Clear error on success and set models
          // Set default model if none selected
          const currentSelected = get().selectedModel
          if (!currentSelected && models.length > 0) {
            const defaultModel = models.find(m => m.default) || models[0]
            console.log('[ModelStore] Setting default model:', defaultModel.id)
            set({ models, selectedModel: defaultModel.id, error: null })
          } else {
            set({ models, error: null })
          }
        } catch (error) {
          console.error('[ModelStore] Error fetching models:', error)
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch models'
          set({ error: errorMessage, isLoading: false, models: [] })
        } finally {
          set({ isLoading: false })
        }
      },
    }),
    {
      name: 'model-storage',
      partialize: (state) => ({
        // Only persist selectedModel, not error or loading state
        selectedModel: state.selectedModel,
      }),
    }
  )
)

