import { useChatStore } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'
import type { DebugChunkType } from '../store/chatStore'

export interface WebSocketEvent {
  type: string
  timestamp: number
  data: any
}

export class WebSocketClient {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  
  // Track current reasoning/answer block IDs per message
  private currentReasoningBlockId: string | null = null
  private currentAnswerBlockId: string | null = null
  private currentMessageId: string | null = null

  connect(sessionId: string): void {
    this.sessionId = sessionId
    this._connect()
  }

  private _connect(): void {
    if (!this.sessionId) {
      console.warn('[WebSocket] Cannot connect: sessionId is null')
      return
    }

    if (this.ws) {
      const state = this.ws.readyState
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
        console.log('[WebSocket] Closing existing connection before creating new one, state:', state)
        this.ws.onclose = null
        this.ws.onerror = null
        this.ws.close()
        this.ws = null
        setTimeout(() => this._doConnect(), 50)
        return
      } else if (state === WebSocket.CLOSING) {
        console.log('[WebSocket] Waiting for existing connection to close')
        this.ws.onclose = () => {
          this.ws = null
          this._doConnect()
        }
        return
      }
    }

    this._doConnect()
  }

  private _doConnect(): void {
    if (!this.sessionId) return

    // Use same-origin WS endpoint.
    // In dev, Vite proxies `/ws` → backend (see `frontend/vite.config.ts`), which avoids
    // localhost/IPv6 issues and keeps WS aligned with REST `/api` proxy behavior.
    const pageProto = window.location.protocol
    const wsProto = pageProto === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${wsProto}://${window.location.host}/ws/${this.sessionId}`
    console.log('[WebSocket] Attempting to connect to:', wsUrl)
    
    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('[WebSocket] Successfully connected to:', wsUrl)
        useChatStore.getState().setConnectionStatus(true)
        this.reconnectAttempts = 0
      }

      this.ws.onmessage = (event) => {
        try {
          const data: WebSocketEvent = JSON.parse(event.data)
          console.log('[WebSocket] Event received:', data.type, data)
          
          // Log react_* events specifically
          if (data.type.startsWith('react_')) {
            console.log('[WebSocket] ReAct event received:', data.type, {
              hasData: !!data.data,
              dataKeys: data.data ? Object.keys(data.data) : [],
              sessionId: this.sessionId
            })
            
            // Send to debug log server
            try {
              fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  location: `websocket.ts:onmessage:react_event`,
                  message: `ReAct event received on frontend`,
                  data: {
                    event_type: data.type,
                    has_data: !!data.data,
                    data_keys: data.data ? Object.keys(data.data) : [],
                    session_id: this.sessionId
                  },
                  timestamp: Date.now(),
                  sessionId: this.sessionId || 'unknown',
                  runId: 'run1',
                  hypothesisId: 'F'
                })
              }).catch(() => {})
            } catch (e) {
              // Ignore fetch errors
            }
          }
          
          this.handleEvent(data)
        } catch (error) {
          console.error('[WebSocket] Error handling message:', error, event.data)
        }
      }

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Connection error:', error)
        console.error('[WebSocket] WebSocket state:', this.ws?.readyState)
      }

      this.ws.onclose = (event) => {
        console.log('[WebSocket] Connection closed. Code:', event.code, 'Reason:', event.reason, 'WasClean:', event.wasClean)
        useChatStore.getState().setConnectionStatus(false)
        
        if (event.wasClean || this.reconnectAttempts > 0) {
          this._attemptReconnect()
        } else {
          console.warn('[WebSocket] Initial connection failed, not attempting reconnect')
        }
      }
    } catch (error) {
      console.error('[WebSocket] Failed to create WebSocket:', error)
      this.ws = null
    }
  }

  private _attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => {
        console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
        this._connect()
      }, this.reconnectDelay * this.reconnectAttempts)
    }
  }

  private handleEvent(event: WebSocketEvent): void {
    const chatStore = useChatStore.getState()
    
    // Helper function to ensure active workflow exists for current user message
    const ensureActiveWorkflow = () => {
      const state = useChatStore.getState()
      // Find the last user message
      const messages = state.messages
      const lastUserMessage = [...messages].reverse().find(m => m.role === 'user')
      const lastUserTimestamp = lastUserMessage?.timestamp
      
      // Check if active workflow matches the last user message
      if (state.activeWorkflowId && state.activeWorkflowId === lastUserTimestamp && state.workflows[state.activeWorkflowId]) {
        return state.activeWorkflowId
      }
      
      // If active workflow doesn't match last user message, create new one
      if (lastUserTimestamp) {
        useChatStore.getState().setActiveWorkflow(lastUserTimestamp)
        return lastUserTimestamp
      }
      
      return null
    }
    const settingsStore = useSettingsStore.getState()
    const debugMode = settingsStore.debugMode
    console.log('[WebSocket] Received event:', event.type, event.data)
    
  
    // Helper function to add debug chunk if debug mode is enabled
    const addDebugChunkIfEnabled = (messageId: string, chunkType: DebugChunkType, content: string, metadata?: Record<string, any>) => {
      if (debugMode) {
        const msgId = messageId || this.currentMessageId || `msg-${Date.now()}`
        chatStore.addDebugChunk(msgId, chunkType, content, metadata)
      }
    }

    try {
      switch (event.type) {
      case 'message':
        // Legacy message event (non-streaming)
        if (event.data.role === 'assistant' || event.data.role === 'system') {
          const messageTimestamp = new Date().toISOString()
          chatStore.addMessage({
            role: event.data.role,
            content: event.data.content,
            timestamp: messageTimestamp,
          })
          chatStore.setAgentTyping(false)
        } else if (event.data.role === 'user') {
          const allMessages = chatStore.getDisplayMessages()
          const lastMessage = allMessages[allMessages.length - 1]
          if (!lastMessage || lastMessage.content !== event.data.content || lastMessage.role !== 'user') {
            chatStore.addMessage({
              role: 'user',
              content: event.data.content,
              timestamp: new Date().toISOString(),
            })
          }
        }
        break

      case 'message_start':
        // Start of a new assistant message
        const messageId = event.data.message_id || `msg-${Date.now()}`
        this.currentMessageId = messageId
        this.currentReasoningBlockId = null
        this.currentAnswerBlockId = null
        chatStore.setAgentTyping(true)
        addDebugChunkIfEnabled(messageId, 'message_start', 'Начало сообщения', event.data)
        console.log('[WebSocket] Starting new message:', messageId)
        break

      case 'thinking':
        // Reasoning/thinking eventchatStore.setAgentTyping(true)
        const thinkingMessage = event.data.message || event.data.step || 'Thinking...'
        
        // Get or create current message ID
        if (!this.currentMessageId) {
          this.currentMessageId = `msg-${Date.now()}`
        }
        const thinkingMsgId = this.currentMessageId
        // Check if we need to create a NEW reasoning block or continue existing one
        let shouldCreateNewReasoningBlock = false
        
        // Case 1: If we have an active answer block, this is a new reasoning cycle
        if (this.currentAnswerBlockId && !this.currentAnswerBlockId.includes('reasoning')) {
          // This means we're starting a new reasoning cycle after an answer
          // Complete the answer block first
          chatStore.completeAnswerBlock(thinkingMsgId, this.currentAnswerBlockId)
          // We need a new reasoning block
          this.currentReasoningBlockId = null
          this.currentAnswerBlockId = null
          shouldCreateNewReasoningBlock = true}
        // Case 2: If we have a reasoning block, check if it's still streaming
        else if (this.currentReasoningBlockId) {
          const currentMessage = useChatStore.getState().assistantMessages[thinkingMsgId]
          const currentReasoningBlock = currentMessage?.reasoningBlocks.find((b: any) => b.id === this.currentReasoningBlockId)
          
          if (currentReasoningBlock) {
            if (currentReasoningBlock.isStreaming) {
              // Reasoning block is still streaming - this is a CONTINUATION of the same block
              // We should UPDATE it, not create a new one
              shouldCreateNewReasoningBlock = false} else {
              // Reasoning block is completed - this is a NEW reasoning block
              shouldCreateNewReasoningBlock = true
              this.currentReasoningBlockId = null}
          } else {
            // Reasoning block not found in store - create new one
            const missingReasoningBlockId = this.currentReasoningBlockId
            shouldCreateNewReasoningBlock = true
            this.currentReasoningBlockId = null
          }
        }
        // Case 3: No reasoning block exists - create new one
        else {
          shouldCreateNewReasoningBlock = true
        }
        
        // Create new reasoning block if needed
        if (shouldCreateNewReasoningBlock) {
          this.currentReasoningBlockId = `reasoning-${Date.now()}`
          chatStore.startReasoningBlock(thinkingMsgId, this.currentReasoningBlockId)
        }
        
        // Update reasoning block content (replace, not append - backend sends accumulated content)
        // At this point, currentReasoningBlockId must be set (either existing or newly created)
        if (!this.currentReasoningBlockId) {
          console.error('[WebSocket] ERROR: currentReasoningBlockId is null when trying to update reasoning block')
          break
        }
        chatStore.updateReasoningBlock(thinkingMsgId, this.currentReasoningBlockId, thinkingMessage)
        addDebugChunkIfEnabled(thinkingMsgId, 'thinking', thinkingMessage, event.data)
        console.log('[WebSocket] Updated reasoning block:', this.currentReasoningBlockId, 'content length:', thinkingMessage.length)
        break

      case 'message_chunk':
        // Streaming answer content
        const chunkContent = event.data.content || ''
        
        // CRITICAL FIX: If event.data.message_id exists and differs from currentMessageId,
        // and we have a reasoning block, we need to move the reasoning block to the new message
        const eventMessageId = event.data.message_id
        let chunkMsgId: string
        
        if (!this.currentMessageId) {
          // No current message, use event message_id or create new
          chunkMsgId = eventMessageId || `msg-${Date.now()}`
          this.currentMessageId = chunkMsgId
        } else if (eventMessageId && eventMessageId !== this.currentMessageId) {
          // Event has different message_id - copy reasoning block to new message
          const oldMessageId = this.currentMessageId
          chunkMsgId = eventMessageId
          
          // CRITICAL: Complete any active reasoning block in old message before switching
          if (this.currentReasoningBlockId && oldMessageId) {
            const state = useChatStore.getState()
            const oldMessage = state.assistantMessages[oldMessageId]
            if (oldMessage) {
              const reasoningBlock = oldMessage.reasoningBlocks.find((b: any) => b.id === this.currentReasoningBlockId)
              if (reasoningBlock && reasoningBlock.isStreaming) {
                // Complete the reasoning block in old message before copying
                chatStore.completeReasoningBlock(oldMessageId, this.currentReasoningBlockId)
              }
            }
          }
          
          this.currentMessageId = chunkMsgId
          
          // Copy reasoning blocks to new message if they exist
          // Check both currentReasoningBlockId and all reasoning blocks in old message
          const state = useChatStore.getState()
          const oldMessage = state.assistantMessages[oldMessageId]
          if (oldMessage && oldMessage.reasoningBlocks.length > 0) {
            // Copy all reasoning blocks from old message to new message
            const existing = state.assistantMessages[chunkMsgId]
            const reasoningBlocksToCopy = oldMessage.reasoningBlocks.filter((b: any) => 
              !existing?.reasoningBlocks.some((eb: any) => eb.id === b.id)
            )
            
            if (reasoningBlocksToCopy.length > 0) {
              // Create new message or update existing
              if (!existing) {
                useChatStore.setState((state) => ({
                  assistantMessages: {
                    ...state.assistantMessages,
                    [chunkMsgId]: {
                      id: chunkMsgId,
                      role: 'assistant',
                      timestamp: new Date().toISOString(),
                      reasoningBlocks: reasoningBlocksToCopy,
                      answerBlocks: [],
                      isComplete: false,
                    },
                  },
                }))
              } else {
                useChatStore.setState((state) => ({
                  assistantMessages: {
                    ...state.assistantMessages,
                    [chunkMsgId]: {
                      ...existing,
                      reasoningBlocks: [...existing.reasoningBlocks, ...reasoningBlocksToCopy],
                    },
                  },
                }))
              }
              
              // Update currentReasoningBlockId to the last reasoning block if it was set
              if (this.currentReasoningBlockId) {
                const reasoningBlock = reasoningBlocksToCopy.find((b: any) => b.id === this.currentReasoningBlockId)
                if (reasoningBlock) {
                  // Keep currentReasoningBlockId
                } else {
                  // Use the last reasoning block from old message
                  const lastReasoningBlock = oldMessage.reasoningBlocks[oldMessage.reasoningBlocks.length - 1]
                  if (lastReasoningBlock) {
                    this.currentReasoningBlockId = lastReasoningBlock.id
                  }
                }
              } else {
                // Use the last reasoning block from old message
                const lastReasoningBlock = oldMessage.reasoningBlocks[oldMessage.reasoningBlocks.length - 1]
                if (lastReasoningBlock) {
                  this.currentReasoningBlockId = lastReasoningBlock.id
                }
              }
            }
          } else if (this.currentReasoningBlockId && oldMessage) {
            // Fallback: copy single reasoning block if currentReasoningBlockId is set
            const reasoningBlock = oldMessage.reasoningBlocks?.find((b: any) => b.id === this.currentReasoningBlockId)
            if (reasoningBlock) {
              // Create reasoning block in new message with same content
              // Use existing methods, then update timestamp to preserve order
              const state = useChatStore.getState()
              const existing = state.assistantMessages[chunkMsgId]
              
              if (!existing) {
                // Create new message with reasoning block
                useChatStore.getState().startReasoningBlock(chunkMsgId, this.currentReasoningBlockId)
                useChatStore.getState().updateReasoningBlock(chunkMsgId, this.currentReasoningBlockId, reasoningBlock.content)
                // Update timestamp to preserve original order
                const updatedState = useChatStore.getState()
                const updatedMessage = updatedState.assistantMessages[chunkMsgId]
                if (updatedMessage) {
                  const updatedBlocks = updatedMessage.reasoningBlocks.map(b =>
                    b.id === this.currentReasoningBlockId
                      ? { ...b, timestamp: reasoningBlock.timestamp }
                      : b
                  )
                  useChatStore.setState((state) => ({
                    assistantMessages: {
                      ...state.assistantMessages,
                      [chunkMsgId]: {
                        ...updatedMessage,
                        reasoningBlocks: updatedBlocks,
                      },
                    },
                  }))
                }
              } else {
                // Add to existing message
                useChatStore.getState().startReasoningBlock(chunkMsgId, this.currentReasoningBlockId)
                useChatStore.getState().updateReasoningBlock(chunkMsgId, this.currentReasoningBlockId, reasoningBlock.content)
                // Update timestamp to preserve original order
                const updatedState = useChatStore.getState()
                const updatedMessage = updatedState.assistantMessages[chunkMsgId]
                if (updatedMessage) {
                  const updatedBlocks = updatedMessage.reasoningBlocks.map(b =>
                    b.id === this.currentReasoningBlockId
                      ? { ...b, timestamp: reasoningBlock.timestamp }
                      : b
                  )
                  useChatStore.setState((state) => ({
                    assistantMessages: {
                      ...state.assistantMessages,
                      [chunkMsgId]: {
                        ...updatedMessage,
                        reasoningBlocks: updatedBlocks,
                      },
                    },
                  }))
                }
              }
            }
          }
        } else {
          // Use existing currentMessageId
          chunkMsgId = this.currentMessageId as string
        }
        
        // CRITICAL: If we have an active reasoning block, complete it (answer is starting)
        // This must happen AFTER we've handled message_id switching, so we use the correct chunkMsgId
        if (this.currentReasoningBlockId) {
          // Verify the reasoning block exists in the current message before completing
          const state = useChatStore.getState()
          const currentMessage = state.assistantMessages[chunkMsgId]
          if (currentMessage) {
            const reasoningBlock = currentMessage.reasoningBlocks.find((b: any) => b.id === this.currentReasoningBlockId)
            if (reasoningBlock) {
              chatStore.completeReasoningBlock(chunkMsgId, this.currentReasoningBlockId)
            }
          }
          this.currentReasoningBlockId = null
        }
        
        // Get or create answer block
        if (!this.currentAnswerBlockId) {
          this.currentAnswerBlockId = `answer-${Date.now()}`
          chatStore.startAnswerBlock(chunkMsgId, this.currentAnswerBlockId)
        }
        
        // Update answer block content (replace, not append - backend sends accumulated content)
        chatStore.updateAnswerBlock(chunkMsgId, this.currentAnswerBlockId, chunkContent)
        addDebugChunkIfEnabled(chunkMsgId, 'message_chunk', chunkContent, { ...event.data, chunk: event.data.chunk })
        console.log('[WebSocket] Updated answer block:', this.currentAnswerBlockId, 'content length:', chunkContent.length)
        break

      case 'message_complete':
        // Complete the message
        const completeMessageId = event.data.message_id || this.currentMessageId
        if (completeMessageId) {
          // Complete any active blocks
          if (this.currentReasoningBlockId) {
            chatStore.completeReasoningBlock(completeMessageId, this.currentReasoningBlockId)
          }
          if (this.currentAnswerBlockId) {
            chatStore.completeAnswerBlock(completeMessageId, this.currentAnswerBlockId)
          }
          
          // Complete the message (moves to regular messages)
          chatStore.completeMessage(completeMessageId)
          addDebugChunkIfEnabled(completeMessageId, 'message_complete', event.data.content || 'Сообщение завершено', event.data)
          
          // Reset state for next message
          // Note: We keep currentMessageId in case there's another reasoning cycle
          // It will be reset when a new message_start arrives
          this.currentReasoningBlockId = null
          this.currentAnswerBlockId = null
        }
        chatStore.setAgentTyping(false)
        console.log('[WebSocket] Completed message:', completeMessageId)
        break

      case 'tool_call':
        // Tool call event (add to reasoning block)
        chatStore.setAgentTyping(true)
        const toolName = event.data.tool_name || event.data.name || 'Unknown tool'
        const toolArgs = event.data.arguments || event.data.args || {}
        
        // Get or create message ID
        const toolMsgId = this.currentMessageId || `msg-${Date.now()}`
        if (!this.currentMessageId) {
          this.currentMessageId = toolMsgId
        }
        
        // Get or create reasoning block
        if (!this.currentReasoningBlockId) {
          this.currentReasoningBlockId = `reasoning-${Date.now()}`
          chatStore.startReasoningBlock(toolMsgId, this.currentReasoningBlockId)
        }
        
        // Append tool call info to reasoning
        const toolCallText = `Вызываю инструмент: ${toolName}${Object.keys(toolArgs).length > 0 ? ` (${Object.keys(toolArgs).slice(0, 3).join(', ')}${Object.keys(toolArgs).length > 3 ? '...' : ''})` : ''}`
        const currentReasoning = chatStore.assistantMessages[toolMsgId]?.reasoningBlocks
          .find((b: any) => b.id === this.currentReasoningBlockId)?.content || ''
        chatStore.updateReasoningBlock(toolMsgId, this.currentReasoningBlockId, currentReasoning + (currentReasoning ? '\n' : '') + toolCallText)
        addDebugChunkIfEnabled(toolMsgId, 'tool_call', toolCallText, { tool_name: toolName, arguments: toolArgs })
        break

      case 'tool_result':
        // Tool result event (add to reasoning block)
        const resultContent = event.data.result || event.data.content || 'Выполнение завершено'
        const resultText = typeof resultContent === 'string' ? resultContent : JSON.stringify(resultContent)
        const compactResult = resultText.length > 1000 
          ? resultText.substring(0, 1000) + '\n\n... (результат обрезан) ...'
          : resultText
        
        // Add to reasoning if we have an active block
        if (!this.currentMessageId) {
          this.currentMessageId = `msg-${Date.now()}`
        }
        const resultMsgId = this.currentMessageId
        if (this.currentReasoningBlockId) {
          const currentReasoning = chatStore.assistantMessages[resultMsgId]?.reasoningBlocks
            .find((b: any) => b.id === this.currentReasoningBlockId)?.content || ''
          chatStore.updateReasoningBlock(resultMsgId, this.currentReasoningBlockId, currentReasoning + (currentReasoning ? '\n' : '') + `Результат: ${compactResult}`)
        }
        addDebugChunkIfEnabled(resultMsgId, 'tool_result', compactResult, event.data)
        break

      case 'plan_request':
        // Handle plan approval request (legacy - keep for compatibility)
        break

      case 'plan_thinking_chunk':
        // Ensure active workflow exists before updating
        ensureActiveWorkflow()
        // Accumulate thinking during plan generation
        useChatStore.getState().updatePlanThinking(event.data.content || '')
        console.log('[WebSocket] Plan thinking chunk:', event.data.content?.substring(0, 50))
        break

      case 'plan_thinking_complete':
        // Stop plan thinking streaming - this ensures the thinking block collapses immediately
        // This event is sent before plan_generated to stop the thinking stream
        ensureActiveWorkflow()
        // Use setState with proper Zustand pattern to update the workflow
        useChatStore.setState((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) return state
          const workflow = state.workflows[activeId]
          if (!workflow?.plan?.planThinkingIsStreaming) return state
          
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                plan: {
                  ...workflow.plan,
                  planThinkingIsStreaming: false
                }
              }
            }
          }
        })
        console.log('[WebSocket] Plan thinking complete - streaming stopped')
        break

      case 'plan_generated':
        // Ensure active workflow exists before setting plan
        ensureActiveWorkflow()
        // Save plan to chatStore - use getState() to get fresh state after set
        useChatStore.getState().setWorkflowPlan(
          event.data.plan || '',
          event.data.steps || [],
          event.data.confirmation_id || null
        )
        console.log('[WebSocket] Plan generated:', event.data.plan)
        break

      case 'awaiting_confirmation':
        // Ensure active workflow exists
        ensureActiveWorkflow()
        // Show confirmation buttons - use getState() to get fresh state
        useChatStore.getState().setAwaitingConfirmation(true)
        console.log('[WebSocket] Awaiting confirmation')
        break

      case 'step_start':
        // Ensure active workflow exists before starting step
        ensureActiveWorkflow()
        // Start a new workflow step - use getState() to get fresh state after set
        useChatStore.getState().startWorkflowStep(event.data.step, event.data.title || `Step ${event.data.step}`)
        console.log('[WebSocket] Step started:', event.data.step, event.data.title)
        break

      case 'thinking_chunk':
        // Ensure active workflow exists
        ensureActiveWorkflow()
        // Add thinking chunk to current step (streaming) - use getState() to get fresh state
        const currentStateForThinking = useChatStore.getState()
        const activeIdForThinking = currentStateForThinking.activeWorkflowId
        if (activeIdForThinking) {
          const workflowForThinking = currentStateForThinking.workflows[activeIdForThinking]
          const currentStep = workflowForThinking?.currentStep
          if (currentStep !== null && currentStep !== undefined) {
            currentStateForThinking.updateStepThinking(currentStep, event.data.content || '')
          }
        }
        break

      case 'response_chunk':
        // Ensure active workflow exists
        ensureActiveWorkflow()
        // Add response chunk to current step (streaming) - use getState() to get fresh state
        const currentStateForResponse = useChatStore.getState()
        const activeIdForResponse = currentStateForResponse.activeWorkflowId
        if (activeIdForResponse) {
          const workflowForResponse = currentStateForResponse.workflows[activeIdForResponse]
          const currentStepForResponse = workflowForResponse?.currentStep
          if (currentStepForResponse !== null && currentStepForResponse !== undefined) {
            currentStateForResponse.updateStepResponse(currentStepForResponse, event.data.content || '')
          }
        }
        break

      case 'step_complete':
        // Complete a workflow step - use getState() to get fresh state
        useChatStore.getState().completeWorkflowStep(event.data.step)
        console.log('[WebSocket] Step completed:', event.data.step)
        break

      case 'workflow_paused':
        console.log('[WebSocket] Workflow paused - requires user help:', event.data)
        // Workflow paused due to critical error requiring user help
        // The step result will contain the help request
        useChatStore.getState().setAgentTyping(false)
        break

      case 'user_assistance_request':
        console.log('[WebSocket] User assistance requested:', event.data)
        // Store the assistance request in chat store
        const assistanceState = useChatStore.getState()
        assistanceState.setUserAssistanceRequest(event.data)
        assistanceState.setAgentTyping(false)
        break

      case 'workflow_stopped':
        console.log('[WebSocket] Workflow stopped by user:', event.data)
        // Workflow stopped by user request
        useChatStore.getState().setAgentTyping(false)
        break

      case 'workflow_complete':
        // Complete the entire workflow - use getState() to get fresh state
        const finalState = useChatStore.getState()
        finalState.completeWorkflow()
        finalState.setAgentTyping(false)
        console.log('[WebSocket] Workflow completed')
        break

      case 'final_result_start':
        // Initialize final result for the active workflow
        const finalResultStartWorkflowId = ensureActiveWorkflow()
        if (finalResultStartWorkflowId) {
          chatStore.updateWorkflowFinalResult(finalResultStartWorkflowId, '')
        }
        console.log('[WebSocket] Final result streaming started')
        break

      case 'final_result_chunk':
        // Update final result with accumulated content (streaming)
        const finalResultChunkWorkflowId = ensureActiveWorkflow()
        if (finalResultChunkWorkflowId) {
          chatStore.updateWorkflowFinalResult(finalResultChunkWorkflowId, event.data.content || '')
        }
        console.log('[WebSocket] Final result chunk received, length:', event.data.content?.length || 0)
        break

      case 'final_result_complete':
        // Complete final result streaming
        const finalResultCompleteWorkflowId = ensureActiveWorkflow()
        if (finalResultCompleteWorkflowId) {
          chatStore.updateWorkflowFinalResult(finalResultCompleteWorkflowId, event.data.content || '')
        }
        chatStore.setAgentTyping(false)
        console.log('[WebSocket] Final result streaming completed')
        break

      case 'final_result':
        // Legacy: Set final result for the active workflow (backward compatibility)
        const finalResultWorkflowId = ensureActiveWorkflow()
        if (finalResultWorkflowId) {
          chatStore.setWorkflowFinalResult(finalResultWorkflowId, event.data.content)
        }
        chatStore.setAgentTyping(false)
        console.log('[WebSocket] Final result received (legacy)')
        break

      case 'error':
        const errorMsgId = this.currentMessageId || `msg-${Date.now()}`
        addDebugChunkIfEnabled(errorMsgId, 'error', event.data.message || 'Ошибка', event.data)
        chatStore.addMessage({
          role: 'system',
          content: `Error: ${event.data.message}`,
          timestamp: new Date().toISOString(),
        })
        // Don't set agentTyping to false here - let message_complete handle it
        // This ensures proper cleanup if message_complete arrives after error
        break

      // Workspace panel events
      case 'sheets_action': {
        console.log('[WebSocket] sheets_action event received:', event.data)
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { 
            spreadsheet_id, 
            spreadsheet_url, 
            title, 
            action, 
            range, 
            description 
          } = event.data

          if (!spreadsheet_id) {
            console.warn('[WebSocket] sheets_action event missing spreadsheet_id:', event.data)
            return
          }
          
          console.log('[WebSocket] Extracted data:', {
            spreadsheet_id,
            spreadsheet_url,
            title,
            action,
            range,
            description
          })
          
          // Force panel visibility first
          const wasVisible = workspaceStore.isPanelVisible
          if (!workspaceStore.isPanelVisible) {
            workspaceStore.togglePanel()
          }

          // Check if tab already exists to prevent duplicates
          const existingTab = workspaceStore.tabs.find(
            t => t.type === 'sheets' && t.data?.spreadsheetId === spreadsheet_id
          )

          if (existingTab) {
            console.log('[WebSocket] Tab already exists for spreadsheet_id:', spreadsheet_id, 'updating and activating')
            // Update existing tab with new action data (addTab will handle this via deduplication)
            workspaceStore.addTab({
              type: 'sheets',
              title: title || existingTab.title || 'Google Sheets',
              url: spreadsheet_url || existingTab.url || (spreadsheet_id 
                ? `https://docs.google.com/spreadsheets/d/${spreadsheet_id}/edit`
                : undefined),
              data: {
                spreadsheetId: spreadsheet_id,
                action: action || 'update',
                range: range || null,
                description: description || '',
                timestamp: Date.now()
              },
              closeable: true,
            })
            // Ensure the tab is active
            workspaceStore.setActiveTab(existingTab.id)
            return
          }
          
          // Create new tab
          workspaceStore.addTab({
            type: 'sheets',
            title: title || 'Google Sheets',
            url: spreadsheet_url || (spreadsheet_id 
              ? `https://docs.google.com/spreadsheets/d/${spreadsheet_id}/edit`
              : undefined),
            data: {
              spreadsheetId: spreadsheet_id,
              action: action || 'update',
              range: range || null,
              description: description || '',
              timestamp: Date.now()
            },
            closeable: true,
          })

          console.log('[WebSocket] Tab added successfully:', {
            action,
            spreadsheet_id,
            range,
            tabsCount: workspaceStore.tabs.length,
            activeTabId: workspaceStore.activeTabId
          })
        }).catch((err) => {
          console.error('[WebSocket] Error handling sheets_action:', err)
        })
        break
      }

      case 'docs_action': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { document_id, document_url, title } = event.data
          workspaceStore.addTab({
            type: 'docs',
            title: title || 'Google Docs',
            url: document_url || (document_id
              ? `https://docs.google.com/document/d/${document_id}/edit`
              : undefined),
            data: { documentId: document_id },
            closeable: true,
          })
          console.log('[WebSocket] Docs action:', document_id)
        })
        break
      }

      case 'slides_action': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { presentation_id, presentation_url, title } = event.data
          workspaceStore.addTab({
            type: 'slides',
            title: title || 'Google Slides',
            url: presentation_url || (presentation_id
              ? `https://docs.google.com/presentation/d/${presentation_id}/edit`
              : undefined),
            data: { presentationId: presentation_id },
            closeable: true,
          })
          console.log('[WebSocket] Slides action:', presentation_id)
        })
        break
      }

      case 'email_preview': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { to, subject, body, attachments } = event.data
          workspaceStore.addTab({
            type: 'email',
            title: `Email: ${subject || 'Без темы'}`,
            data: { to, subject, body, attachments },
            closeable: true,
          })
          console.log('[WebSocket] Email preview:', subject)
        })
        break
      }

      case 'dashboard_ready': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { title, url, data } = event.data
          workspaceStore.addTab({
            type: 'dashboard',
            title: title || 'Dashboard',
            url: url,
            data: data,
            closeable: true,
          })
          console.log('[WebSocket] Dashboard ready:', url)
        })
        break
      }

      case 'chart_data': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { title, chartType, series, options } = event.data
          workspaceStore.addTab({
            type: 'chart',
            title: title || 'Chart',
            data: { chartType, series, options },
            closeable: true,
          })
          console.log('[WebSocket] Chart data:', chartType)
        })
        break
      }

      case 'code_display': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { filename, language, code } = event.data
          workspaceStore.addTab({
            type: 'code',
            title: filename || 'Code',
            data: { language: language || 'python', code, filename },
            closeable: true,
          })
          console.log('[WebSocket] Code display:', filename, language)
        })
        break
      }

      case 'calendar_view': {
        import('../store/workspaceStore').then(({ useWorkspaceStore }) => {
          const workspaceStore = useWorkspaceStore.getState()
          const { title, mode, calendarId, events } = event.data
          workspaceStore.addTab({
            type: 'calendar',
            title: title || 'Calendar',
            data: { mode: mode || 'iframe', calendarId: calendarId || 'primary', events },
            closeable: true,
          })
          console.log('[WebSocket] Calendar view:', mode, calendarId)
        })
        break
      }

      case 'react_start': {
        // ReAct cycle started
        console.log('[WebSocket] ReAct cycle started:', event.data)
        console.log('[WebSocket] Current message ID:', this.currentMessageId)
        console.log('[WebSocket] Current reasoning block ID:', this.currentReasoningBlockId)
        
        const reactMsgId = this.currentMessageId || `msg-${Date.now()}`
        this.currentMessageId = reactMsgId
        chatStore.setAgentTyping(true)
        
        // Create reasoning block for ReAct trail
        this.currentReasoningBlockId = `react-reasoning-${Date.now()}`
        console.log('[WebSocket] Created reasoning block ID:', this.currentReasoningBlockId)
        
        chatStore.startReasoningBlock(reactMsgId, this.currentReasoningBlockId)
        
        const goal = event.data.goal || 'Выполнение задачи...'
        const content = `🔄 **Запуск ReAct цикла...**\n\nЦель: ${goal}`
        console.log('[WebSocket] Updating reasoning block with content length:', content.length)
        
        chatStore.updateReasoningBlock(reactMsgId, this.currentReasoningBlockId, content)
        
        // Verify the block was created
        const state = useChatStore.getState()
        const message = state.assistantMessages[reactMsgId]
        console.log('[WebSocket] Message after update:', message ? {
          id: message.id,
          reasoningBlocksCount: message.reasoningBlocks.length,
          firstBlockContent: message.reasoningBlocks[0]?.content?.substring(0, 50)
        } : 'Message not found')
        
        addDebugChunkIfEnabled(reactMsgId, 'thinking', `ReAct started: ${goal}`, event.data)
        break
      }

      case 'react_thinking': {
        // ReAct thinking phase
        console.log('[WebSocket] ReAct thinking:', event.data)
        const thinkingMsgId = this.currentMessageId || `msg-${Date.now()}`
        if (!this.currentMessageId) {
          this.currentMessageId = thinkingMsgId
        }
        
        // Ensure reasoning block exists
        if (!this.currentReasoningBlockId) {
          this.currentReasoningBlockId = `react-reasoning-${Date.now()}`
          chatStore.startReasoningBlock(thinkingMsgId, this.currentReasoningBlockId)
        }
        
        const thought = event.data.thought || 'Анализирую ситуацию...'
        const iteration = event.data.iteration || 1
        const thinkingContent = `**Итерация ${iteration} - Анализ:**\n\n${thought}`
        chatStore.updateReasoningBlock(thinkingMsgId, this.currentReasoningBlockId, thinkingContent)
        addDebugChunkIfEnabled(thinkingMsgId, 'thinking', thought, event.data)
        break
      }

      case 'react_action': {
        // ReAct action phase
        console.log('[WebSocket] ReAct action:', event.data)
        const actionMsgId = this.currentMessageId || `msg-${Date.now()}`
        if (!this.currentMessageId) {
          this.currentMessageId = actionMsgId
        }
        
        // Ensure reasoning block exists
        if (!this.currentReasoningBlockId) {
          this.currentReasoningBlockId = `react-reasoning-${Date.now()}`
          chatStore.startReasoningBlock(actionMsgId, this.currentReasoningBlockId)
        }
        
        const action = event.data.action || 'Выполнение действия...'
        const tool = event.data.tool || 'unknown'
        const iteration = event.data.iteration || 1
        const actionContent = `**Итерация ${iteration} - Действие:**\n\n🔧 **Инструмент:** \`${tool}\`\n📝 **Описание:** ${action}`
        chatStore.updateReasoningBlock(actionMsgId, this.currentReasoningBlockId, actionContent)
        addDebugChunkIfEnabled(actionMsgId, 'tool_call', `Tool: ${tool}`, event.data)
        break
      }

      case 'react_observation': {
        // ReAct observation phase
        console.log('[WebSocket] ReAct observation:', event.data)
        const obsMsgId = this.currentMessageId || `msg-${Date.now()}`
        if (!this.currentMessageId) {
          this.currentMessageId = obsMsgId
        }
        
        // Ensure reasoning block exists
        if (!this.currentReasoningBlockId) {
          this.currentReasoningBlockId = `react-reasoning-${Date.now()}`
          chatStore.startReasoningBlock(obsMsgId, this.currentReasoningBlockId)
        }
        
        const result = event.data.result || 'Результат получен'
        const iteration = event.data.iteration || 1
        const obsContent = `**Итерация ${iteration} - Наблюдение:**\n\n📊 **Результат:** ${result.substring(0, 500)}${result.length > 500 ? '...' : ''}`
        chatStore.updateReasoningBlock(obsMsgId, this.currentReasoningBlockId, obsContent)
        addDebugChunkIfEnabled(obsMsgId, 'tool_result', result, event.data)
        break
      }

      case 'react_adapting': {
        // ReAct adaptation phase
        console.log('[WebSocket] ReAct adapting:', event.data)
        const adaptMsgId = this.currentMessageId || `msg-${Date.now()}`
        if (!this.currentMessageId) {
          this.currentMessageId = adaptMsgId
        }
        
        // Ensure reasoning block exists
        if (!this.currentReasoningBlockId) {
          this.currentReasoningBlockId = `react-reasoning-${Date.now()}`
          chatStore.startReasoningBlock(adaptMsgId, this.currentReasoningBlockId)
        }
        
        const reason = event.data.reason || 'Адаптация стратегии...'
        const newStrategy = event.data.new_strategy || 'Продолжение выполнения'
        const iteration = event.data.iteration || 1
        const adaptContent = `**Итерация ${iteration} - Адаптация:**\n\n🔄 **Причина:** ${reason}\n📋 **Новая стратегия:** ${newStrategy}`
        chatStore.updateReasoningBlock(adaptMsgId, this.currentReasoningBlockId, adaptContent)
        addDebugChunkIfEnabled(adaptMsgId, 'thinking', `Adapting: ${newStrategy}`, event.data)
        break
      }

      case 'react_complete': {
        // ReAct cycle completed successfully
        console.log('[WebSocket] ReAct cycle completed:', event.data)
        const completeMsgId = this.currentMessageId || `msg-${Date.now()}`
        
        // Complete reasoning block
        if (this.currentReasoningBlockId) {
          chatStore.completeReasoningBlock(completeMsgId, this.currentReasoningBlockId)
        }
        
        // Add final result
        const result = event.data.result || 'Задача выполнена успешно'
        const trail = event.data.trail || []
        
        // Create answer block with result
        this.currentAnswerBlockId = `answer-${Date.now()}`
        chatStore.startAnswerBlock(completeMsgId, this.currentAnswerBlockId)
        chatStore.updateAnswerBlock(completeMsgId, this.currentAnswerBlockId, `✅ **Задача выполнена!**\n\n${result}`)
        chatStore.completeAnswerBlock(completeMsgId, this.currentAnswerBlockId)
        
        chatStore.setAgentTyping(false)
        addDebugChunkIfEnabled(completeMsgId, 'message_complete', result, event.data)
        break
      }

      case 'react_failed': {
        // ReAct cycle failed
        console.log('[WebSocket] ReAct cycle failed:', event.data)
        const failedMsgId = this.currentMessageId || `msg-${Date.now()}`
        
        // Complete reasoning block
        if (this.currentReasoningBlockId) {
          chatStore.completeReasoningBlock(failedMsgId, this.currentReasoningBlockId)
        }
        
        const reason = event.data.reason || 'Неизвестная ошибка'
        const tried = event.data.tried || []
        
        // Create answer block with error
        this.currentAnswerBlockId = `answer-${Date.now()}`
        chatStore.startAnswerBlock(failedMsgId, this.currentAnswerBlockId)
        chatStore.updateAnswerBlock(failedMsgId, this.currentAnswerBlockId, `❌ **Задача не выполнена**\n\n**Причина:** ${reason}\n\n**Попытки:** ${tried.join(', ') || 'нет'}`)
        chatStore.completeAnswerBlock(failedMsgId, this.currentAnswerBlockId)
        
        chatStore.setAgentTyping(false)
        addDebugChunkIfEnabled(failedMsgId, 'error', reason, event.data)
        break
      }

      case 'file_preview': {
        // Handle file preview event for workflow steps
        ensureActiveWorkflow()
        import('../store/chatStore').then(({ useChatStore }) => {
          const chatStore = useChatStore.getState()
          const { step, type, title, subtitle, fileId, fileUrl, previewData } = event.data
          
          if (step) {
            chatStore.setStepFilePreview(step, {
              type: type as 'sheets' | 'docs' | 'slides' | 'code' | 'email' | 'chart',
              title: title || 'File',
              subtitle,
              fileId: fileId || '',
              fileUrl,
              previewData: previewData || {}
            })
            console.log('[WebSocket] File preview set for step:', step, type, title)
          }
        })
        break
      }
      }
    } catch (error) {
      console.error('[WebSocket] Error handling event:', event.type, error, event.data)
      // Don't throw - we want to continue processing future events
    }
  }

  sendMessage(message: string): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        const payload = JSON.stringify({
          type: 'message',
          content: message,
        })
        this.ws.send(payload)
        return true
      } catch (error) {
        console.error('Error sending WebSocket message:', error)
        return false
      }
    }return false
  }

  isConnected(): boolean {
    const connected = this.ws !== null && this.ws.readyState === WebSocket.OPEN
    return connected
  }

  approvePlan(confirmationId: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'approve_plan',
        confirmation_id: confirmationId,
      }))
      console.log('[WebSocket] Plan approved:', confirmationId)
    }
  }

  rejectPlan(confirmationId: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'reject_plan',
        confirmation_id: confirmationId,
      }))
      console.log('[WebSocket] Plan rejected:', confirmationId)
      // Clear workflow state after rejection
      useChatStore.getState().clearWorkflow()
    }
  }

  stopGeneration(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'stop_generation',
      }))
      console.log('[WebSocket] Stop generation requested')
      // NOTE: Do NOT disconnect here - it closes the connection before the server can process the stop_generation message
      // The connection should remain open to receive workflow_stopped event
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    // Reset state
    this.currentMessageId = null
    this.currentReasoningBlockId = null
    this.currentAnswerBlockId = null
  }
}

export const wsClient = new WebSocketClient()
