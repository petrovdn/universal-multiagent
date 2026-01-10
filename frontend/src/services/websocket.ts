import { useChatStore } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'

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
  
  // Thinking block delay (2 seconds)
  private thinkingDelayTimer: ReturnType<typeof setTimeout> | null = null
  private pendingThinkingId: string | null = null
  
  // Intent block minimum display time (1.5 seconds)
  private intentStartTimes: Record<string, number> = {}
  private pendingIntentCompletes: Record<string, { autoCollapse: boolean; summary?: string }> = {}

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
    console.log('[WebSocket] Received event:', event.type, event.data)

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
        console.log('[WebSocket] Updated answer block:', this.currentAnswerBlockId, 'content length:', chunkContent.length)
        break

      case 'message_complete':
        // Cancel thinking delay timer if response completed quickly
        if (this.thinkingDelayTimer) {
          clearTimeout(this.thinkingDelayTimer)
          this.thinkingDelayTimer = null
          console.log('[WebSocket] Cancelled thinking delay - response completed quickly')
        }
        // Clear pending thinking ID
        this.pendingThinkingId = null
        
        // Complete the message
        let completeMessageId = event.data.message_id || this.currentMessageId
        
        // Check if assistantMessages entry exists for this ID (get fresh state)
        const existingAssistantMsg = useChatStore.getState().assistantMessages[completeMessageId]
        
        // If no message exists in assistantMessages (no prior message_start), create a new message with the content
        // FIX: Changed condition from (!completeMessageId && event.data.content) to check if assistantMsg doesn't exist
        if (!existingAssistantMsg && event.data.content) {
          if (!completeMessageId) {
            completeMessageId = `msg-${Date.now()}`
          }
          // Create a new assistant message by starting an answer block
          const answerBlockId = `answer-${Date.now()}`
          chatStore.startAnswerBlock(completeMessageId, answerBlockId)
          chatStore.updateAnswerBlock(completeMessageId, answerBlockId, event.data.content)
          chatStore.completeAnswerBlock(completeMessageId, answerBlockId)
          this.currentMessageId = completeMessageId
        }
        
        if (completeMessageId) {
          // Complete any active blocks
          if (this.currentReasoningBlockId) {
            chatStore.completeReasoningBlock(completeMessageId, this.currentReasoningBlockId)
          }
          if (this.currentAnswerBlockId) {
            chatStore.completeAnswerBlock(completeMessageId, this.currentAnswerBlockId)
          }
          
          // Get final content from answer blocks
          const state = useChatStore.getState()
          const assistantMsg = state.assistantMessages[completeMessageId]
          const finalContent = assistantMsg?.answerBlocks
            .map(block => block.content)
            .join('\n\n')
            .trim() || event.data.content || ''
          
          // For Query and Agent modes with workflow, save to workflow.finalResult instead of regular messages
          if (state.activeWorkflowId && finalContent) {
            // Check execution mode
            const settingsState = useSettingsStore.getState()
            const isQueryMode = settingsState.executionMode === 'query'
            const isAgentMode = settingsState.executionMode === 'agent'
            
            if (isQueryMode || isAgentMode) {
              // Save to workflow finalResult for Query and Agent modes
              chatStore.setWorkflowFinalResult(state.activeWorkflowId, finalContent)
            } else {
              // Complete the message (moves to regular messages)
              chatStore.completeMessage(completeMessageId)
            }
          } else {
            // No workflow - complete normally
            chatStore.completeMessage(completeMessageId)
          }
          
          
          // Reset state for next message
          // Note: We keep currentMessageId in case there's another reasoning cycle
          // It will be reset when a new message_start arrives
          this.currentReasoningBlockId = null
          this.currentAnswerBlockId = null
        }
        
        chatStore.setAgentTyping(false)
        chatStore.clearCurrentAction()
        
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

      case 'step_thinking_chunk':
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
          // Don't reset if we already have content (avoid race conditions)
          const currentContent = useChatStore.getState().workflows[finalResultStartWorkflowId]?.finalResult
          if (!currentContent) {
            chatStore.updateWorkflowFinalResult(finalResultStartWorkflowId, '')
          }
        }
        console.log('[WebSocket] Final result streaming started')
        break

      case 'final_result_chunk':
        // Update final result with accumulated content (streaming)
        const finalResultChunkWorkflowId = ensureActiveWorkflow()
        if (finalResultChunkWorkflowId) {
          chatStore.updateWorkflowFinalResult(finalResultChunkWorkflowId, event.data.content || '')
          console.log('[WebSocket] Final result chunk received, length:', event.data.content?.length || 0)
        }
        break

      case 'final_result_complete':
        // Cancel thinking delay timer if response completed quickly
        if (this.thinkingDelayTimer) {
          clearTimeout(this.thinkingDelayTimer)
          this.thinkingDelayTimer = null
          console.log('[WebSocket] Cancelled thinking delay - final result completed quickly')
        }
        // Clear pending thinking ID
        this.pendingThinkingId = null
        
        // Complete final result streaming - only update if content is longer than current
        const finalResultCompleteWorkflowId = ensureActiveWorkflow()
        const isAgentTypingBeforeFinal = useChatStore.getState().isAgentTyping
        if (finalResultCompleteWorkflowId) {
          const currentFinalContent = useChatStore.getState().workflows[finalResultCompleteWorkflowId]?.finalResult || ''
          const newContent = event.data.content || ''
          // Only update if new content is not shorter (avoid overwriting with truncated content)
          if (newContent.length >= currentFinalContent.length) {
            chatStore.updateWorkflowFinalResult(finalResultCompleteWorkflowId, newContent)
          }
          console.log('[WebSocket] Final result complete, current:', currentFinalContent.length, 'new:', newContent.length)
        }
        chatStore.setAgentTyping(false)
        const isAgentTypingAfterFinal = useChatStore.getState().isAgentTyping
        console.log('[WebSocket] Final result streaming completed')
        break

      case 'final_result': {
        // Legacy: Set final result for the active workflow
        // This is used for:
        // 1. Simple queries (_answer_directly) - no streaming
        // 2. Timeout/error scenarios
        // BUT: Don't overwrite if streaming already provided longer content
        const finalResultWorkflowId = ensureActiveWorkflow()
        if (finalResultWorkflowId) {
          const currentContent = useChatStore.getState().workflows[finalResultWorkflowId]?.finalResult || ''
          const newContent = event.data.content || ''
          
          // Only update if:
          // 1. No current content (simple query case)
          // 2. New content is longer (streaming didn't happen or was shorter)
          if (!currentContent || newContent.length >= currentContent.length) {
            chatStore.setWorkflowFinalResult(finalResultWorkflowId, newContent)
            console.log('[WebSocket] Final result set:', newContent.length, 'chars')
          } else {
            console.log('[WebSocket] Final result skipped (streaming provided longer content):', currentContent.length, '>', newContent.length)
          }
          // Collapse all intents when final result arrives
          chatStore.collapseAllIntents(finalResultWorkflowId)
        }
        chatStore.setAgentTyping(false)
        break
      }

      case 'error':
        const errorMsgId = this.currentMessageId || `msg-${Date.now()}`
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

      // New thinking events (Cursor-style)
      case 'thinking_started': {
        console.log('[WebSocket] Thinking started:', event.data)
        const thinkingId = event.data.thinking_id || `thinking-${Date.now()}`
        
        // Create thinking block but don't show it immediately
        chatStore.startThinking(thinkingId)
        chatStore.setAgentTyping(true)
        
        // Store thinking ID for delayed activation
        this.pendingThinkingId = thinkingId
        
        // Clear any existing timer
        if (this.thinkingDelayTimer) {
          clearTimeout(this.thinkingDelayTimer)
        }
        
        // Set timer to show thinking block after 1.5 seconds
        this.thinkingDelayTimer = setTimeout(() => {
          const stateBeforeCheck = useChatStore.getState()
          const blockBeforeCheck = stateBeforeCheck.thinkingBlocks[thinkingId]
          // Only show if response hasn't completed yet
          const state = useChatStore.getState()
          const block = state.thinkingBlocks[thinkingId]
          if (this.pendingThinkingId === thinkingId && state.activeThinkingId !== thinkingId && block?.status !== 'completed') {
            chatStore.setActiveThinking(thinkingId)
            console.log('[WebSocket] Showing thinking block after 2s delay')
          } else {
          }
          this.thinkingDelayTimer = null
        }, 1500)
        
        break
      }

      case 'thinking_chunk': {
        console.log('[WebSocket] Thinking chunk:', event.data)
        const thinkingId = event.data.thinking_id || useChatStore.getState().activeThinkingId
        if (!thinkingId) {
          // Fallback: create thinking block if doesn't exist
          const newThinkingId = `thinking-${Date.now()}`
          chatStore.startThinking(newThinkingId)
          chatStore.appendThinkingChunk(newThinkingId, event.data.chunk || '', event.data.elapsed_seconds || 0, event.data.step_type)
        } else {
          chatStore.appendThinkingChunk(thinkingId, event.data.chunk || '', event.data.elapsed_seconds || 0, event.data.step_type)
        }
        break
      }

      case 'thinking_completed': {
        const stateBeforeComplete = useChatStore.getState()
        console.log('[WebSocket] Thinking completed:', event.data)
        const thinkingId = event.data.thinking_id || useChatStore.getState().activeThinkingId
        if (thinkingId) {
          // Cancel timer if it's for this thinkingId
          if (this.thinkingDelayTimer && this.pendingThinkingId === thinkingId) {
            clearTimeout(this.thinkingDelayTimer)
            this.thinkingDelayTimer = null
            this.pendingThinkingId = null
          }
          const autoCollapse = event.data.auto_collapse !== false // Default true
          chatStore.completeThinking(thinkingId, autoCollapse)
          const stateAfterComplete = useChatStore.getState()
          // Если есть полный текст, обновляем контент
          if (event.data.full_content) {
            const thinkingState = useChatStore.getState()
            const block = thinkingState.thinkingBlocks[thinkingId]
            if (block) {
              // Обновляем контент через appendThinkingChunk
              chatStore.appendThinkingChunk(thinkingId, event.data.full_content, event.data.elapsed_seconds || block.elapsedSeconds)
            }
          }
        }
        
        // Переключаем intent фазу на 'executing'
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = state.activeIntentId
        if (workflowId && intentId) {
          chatStore.setIntentPhase(workflowId, intentId, 'executing')
        }
        break
      }

      // Intent events (Cursor-style)
      case 'intent_start': {
        console.log('[WebSocket] Intent started:', event.data)
        // Скрываем индикатор "Думаю..." при появлении первого intent
        chatStore.setShowThinkingIndicator(false)
        
        const workflowId = ensureActiveWorkflow()
        if (workflowId) {
          const intentId = event.data.intent_id || `intent-${Date.now()}`
          // Support both 'text' (preferred) and 'intent' (legacy) fields
          const intentText = event.data.text || event.data.intent || 'Выполняю действие...'
          
          // Collapse PREVIOUS intent when new one starts
          const state = useChatStore.getState()
          const previousIntentId = state.activeIntentId
          if (previousIntentId && previousIntentId !== intentId) {
            chatStore.collapseIntent(workflowId, previousIntentId)
          }
          
          // Save start time for minimum display duration
          this.intentStartTimes[intentId] = Date.now()
          
          chatStore.startIntent(workflowId, intentId, intentText)
          chatStore.setAgentTyping(true)
        }
        break
      }

      case 'intent_detail': {
        console.log('[WebSocket] Intent detail:', event.data)
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = event.data.intent_id || state.activeIntentId
        
        if (workflowId && intentId) {
          // Переключаем на фазу executing при получении detail
          chatStore.setIntentPhase(workflowId, intentId, 'executing')
          chatStore.addIntentDetail(workflowId, intentId, {
            type: event.data.type || 'execute',
            description: event.data.description || '',
            timestamp: Date.now(),
          })
        }
        break
      }

      case 'intent_thinking_clear': {
        // Clear thinking text before new iteration
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = event.data.intent_id || state.activeIntentId
        
        if (workflowId && intentId) {
          chatStore.clearIntentThinking(workflowId, intentId)
        }
        break
      }

      case 'intent_thinking_append': {
        // Streaming thinking text - append to existing thinkingText
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = event.data.intent_id || state.activeIntentId
        
        if (workflowId && intentId && event.data.text) {
          chatStore.appendIntentThinking(workflowId, intentId, event.data.text)
        }
        break
      }

      // SmartProgress events
      case 'smart_progress_start': {
        console.log('[WebSocket] SmartProgress started:', event.data)
        const estimatedSec = event.data.estimated_duration_sec || 5
        const goal = event.data.goal || ''
        chatStore.startSmartProgress(estimatedSec, goal)
        break
      }
      
      case 'smart_progress_message': {
        console.log('[WebSocket] SmartProgress message:', event.data)
        const state = useChatStore.getState()
        if (state.smartProgress) {
          const message = event.data.message || 'Обрабатываю...'
          chatStore.updateSmartProgress(
            message,
            state.smartProgress.elapsedSec,
            state.smartProgress.estimatedSec,
            state.smartProgress.progressPercent
          )
        }
        break
      }
      
      case 'smart_progress_timer': {
        const elapsedSec = event.data.elapsed_sec || 0
        const estimatedSec = event.data.estimated_sec || 5
        const progressPercent = event.data.progress_percent || 0
        const state = useChatStore.getState()
        if (state.smartProgress) {
          chatStore.updateSmartProgress(
            state.smartProgress.message,
            elapsedSec,
            estimatedSec,
            progressPercent
          )
        }
        // Также обновляем progress в активном intent
        const workflowId = state.activeWorkflowId
        const intentId = state.activeIntentId
        if (workflowId && intentId) {
          chatStore.setIntentProgress(workflowId, intentId, progressPercent, elapsedSec, estimatedSec)
        }
        break
      }
      
      case 'intent_complete': {
        console.log('[WebSocket] Intent completed:', event.data)
        // Останавливаем SmartProgress при завершении intent
        chatStore.stopSmartProgress()
        
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = event.data.intent_id || state.activeIntentId
        
        if (workflowId && intentId) {
          // DON'T auto-collapse here - collapse happens when NEXT intent starts or final result arrives
          const autoCollapse = false  // Changed: don't collapse immediately
          const summary = event.data.summary // "Найдено 5 встреч"
          
          // Minimum display time: 1.5 seconds
          const MIN_DISPLAY_TIME = 1500
          const startTime = this.intentStartTimes[intentId]
          const elapsed = startTime ? Date.now() - startTime : MIN_DISPLAY_TIME
          
          if (elapsed < MIN_DISPLAY_TIME) {
            // Delay completion to show animation
            const delay = MIN_DISPLAY_TIME - elapsed
            console.log(`[WebSocket] Delaying intent complete by ${delay}ms`)
            setTimeout(() => {
              chatStore.completeIntent(workflowId, intentId, autoCollapse, summary)
              delete this.intentStartTimes[intentId]
            }, delay)
          } else {
            // Already shown long enough, complete immediately
            chatStore.completeIntent(workflowId, intentId, autoCollapse, summary)
            delete this.intentStartTimes[intentId]
          }
        }
        break
      }

      case 'operation_start': {
        console.log('[WebSocket] Operation started:', event.data)
        // #region agent log - H2: Track operation title for dots issue
        const title = event.data.title || 'Выполняем операцию'
        const logData = {
          location: 'websocket.ts:1223',
          message: 'Operation start received',
          data: { 
            title, 
            titleLength: title?.length,
            titleHasDots: title?.includes('...') || title?.includes('…'),
            titleHasThreeDots: (title?.match(/\./g) || []).length >= 3
          },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'H2'
        }
        fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(logData)
        }).catch(() => {})
        // #endregion
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = event.data.intent_id || state.activeIntentId
        const operationId = event.data.operation_id
        
        if (workflowId && intentId && operationId) {
          chatStore.startOperation(
            workflowId,
            operationId,
            intentId,
            title,
            event.data.streaming_title || 'Операция',
            event.data.operation_type || 'read',
            event.data.file_id,
            event.data.file_url,
            event.data.file_type
          )
        }
        break
      }
      
      case 'operation_data': {
        console.log('[WebSocket] Operation data:', event.data)
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = state.activeIntentId
        const operationId = event.data.operation_id
        const data = event.data.data
        
        if (workflowId && intentId && operationId && data) {
          chatStore.addOperationData(workflowId, intentId, operationId, data)
        }
        break
      }
      
      case 'operation_end': {
        console.log('[WebSocket] Operation ended:', event.data)
        const state = useChatStore.getState()
        const workflowId = state.activeWorkflowId
        const intentId = state.activeIntentId
        const operationId = event.data.operation_id
        const summary = event.data.summary
        
        if (workflowId && intentId && operationId && summary) {
          chatStore.completeOperation(workflowId, intentId, operationId, summary)
        }
        break
      }
      
      case 'react_start': {
        // ReAct cycle started - FALLBACK: create thinking block
        console.log('[WebSocket] ReAct cycle started (fallback to thinking):', event.data)
        const thinkingId = `thinking-${Date.now()}`
        
        // Create thinking block but don't show it immediately
        chatStore.startThinking(thinkingId)
        
        // Store thinking ID for delayed activation
        this.pendingThinkingId = thinkingId
        
        // Clear any existing timer
        if (this.thinkingDelayTimer) {
          clearTimeout(this.thinkingDelayTimer)
        }
        
        // Set timer to show thinking block after 1.5 seconds
        this.thinkingDelayTimer = setTimeout(() => {
          // Only show if response hasn't completed yet
          const state = useChatStore.getState()
          if (this.pendingThinkingId === thinkingId && state.activeThinkingId !== thinkingId) {
            chatStore.setActiveThinking(thinkingId)
            console.log('[WebSocket] Showing thinking block after 2s delay (react_start)')
          }
          this.thinkingDelayTimer = null
        }, 1500)
        
        // Also handle legacy reasoning block
        console.log('[WebSocket] Current message ID:', this.currentMessageId)
        console.log('[WebSocket] Current reasoning block ID:', this.currentReasoningBlockId)
        
        const reactMsgId = this.currentMessageId || `msg-${Date.now()}`
        this.currentMessageId = reactMsgId
        
        // Only set isAgentTyping=true if there's an active workflow or message
        // This prevents setting it for background processes or stale events
        const hasActiveWorkflow = chatStore.activeWorkflowId && chatStore.workflows[chatStore.activeWorkflowId]
        const hasActiveMessage = chatStore.assistantMessages[reactMsgId] && !chatStore.assistantMessages[reactMsgId].isComplete
        
        if (hasActiveWorkflow || hasActiveMessage || !chatStore.isAgentTyping) {
          chatStore.setAgentTyping(true)
        } else {
        }
        
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
        
        break
      }

      case 'react_thinking': {
        // ReAct thinking phase - FALLBACK: update thinking block
        console.log('[WebSocket] ReAct thinking (fallback to thinking):', event.data)
        
        // Update thinking block if exists, or create new one
        const thinkingState = useChatStore.getState()
        let thinkingId = thinkingState.activeThinkingId
        if (!thinkingId) {
          // Create thinking block if it doesn't exist
          thinkingId = `thinking-${Date.now()}`
          chatStore.startThinking(thinkingId)
        }
        
        const thoughtText = event.data.thought || 'Анализирую ситуацию...'
        const block = thinkingState.thinkingBlocks[thinkingId]
        const elapsedSeconds = block ? (Date.now() - block.startedAt) / 1000 : 0
        chatStore.appendThinkingChunk(thinkingId, `🧠 ${thoughtText}\n`, elapsedSeconds, 'analyzing')
        
        // Legacy reasoning block handling
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
        
        // Append to existing content instead of replacing
        const reasoningState = useChatStore.getState()
        const message = reasoningState.assistantMessages[thinkingMsgId]
        const existingContent = message?.reasoningBlocks.find(b => b.id === this.currentReasoningBlockId)?.content || ''
        
        const thinkingContent = existingContent 
          ? `${existingContent}\n\n**Итерация ${iteration} - Анализ:**\n\n${thought}`
          : `**Итерация ${iteration} - Анализ:**\n\n${thought}`
        
        console.log('[WebSocket] Updating reasoning block with thinking content, length:', thinkingContent.length)
        chatStore.updateReasoningBlock(thinkingMsgId, this.currentReasoningBlockId, thinkingContent)
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
        
        // Update thinking block if exists, or create new one
        const actionThinkingState = useChatStore.getState()
        let thinkingId = actionThinkingState.activeThinkingId
        if (!thinkingId) {
          // Create thinking block if it doesn't exist
          thinkingId = `thinking-${Date.now()}`
          chatStore.startThinking(thinkingId)
        }
        
        if (thinkingId) {
          // Трансформируем технические сообщения в human-readable
          let humanReadable = action
          if (action.includes('Fallback: использование')) {
            humanReadable = '🔍 Ищу информацию...'
          } else if (tool.includes('calendar') || tool.includes('event')) {
            humanReadable = `📅 Получаю события календаря...`
          } else if (tool.includes('email') || tool.includes('gmail')) {
            humanReadable = `📧 Ищу в почте...`
          } else if (tool.includes('file') || tool.includes('workspace')) {
            humanReadable = `📁 Ищу файлы...`
          } else if (tool.includes('search')) {
            humanReadable = `🔍 Ищу информацию...`
          } else {
            humanReadable = action
          }
          
          const elapsedSeconds = (Date.now() - actionThinkingState.thinkingBlocks[thinkingId].startedAt) / 1000
          chatStore.appendThinkingChunk(thinkingId, `${humanReadable}\n`, elapsedSeconds, 'executing')
        }
        
        
        // Set current action for dynamic indicator
        chatStore.setCurrentAction({ tool, description: action })
        
        const stateAfter = useChatStore.getState()
        
        // Append to existing content instead of replacing
        const actionReasoningState = useChatStore.getState()
        const message = actionReasoningState.assistantMessages[actionMsgId]
        const existingContent = message?.reasoningBlocks.find(b => b.id === this.currentReasoningBlockId)?.content || ''
        
        const actionContent = existingContent
          ? `${existingContent}\n\n**Итерация ${iteration} - Действие:**\n\n🔧 **Инструмент:** \`${tool}\`\n📝 **Описание:** ${action}`
          : `**Итерация ${iteration} - Действие:**\n\n🔧 **Инструмент:** \`${tool}\`\n📝 **Описание:** ${action}`
        
        console.log('[WebSocket] Updating reasoning block with action content, length:', actionContent.length)
        chatStore.updateReasoningBlock(actionMsgId, this.currentReasoningBlockId, actionContent)
        break
      }

      case 'react_observation': {
        // ReAct observation phase - FALLBACK: update thinking block
        console.log('[WebSocket] ReAct observation (fallback to thinking):', event.data)
        
        // Update thinking block if exists, or create new one
        const obsThinkingState = useChatStore.getState()
        let thinkingId = obsThinkingState.activeThinkingId
        if (!thinkingId) {
          // Create thinking block if it doesn't exist
          thinkingId = `thinking-${Date.now()}`
          chatStore.startThinking(thinkingId)
        }
        
        if (thinkingId) {
          const result = event.data.result || 'Результат получен'
          const resultPreview = result.length > 100 ? result.substring(0, 100) + '...' : result
          const elapsedSeconds = (Date.now() - obsThinkingState.thinkingBlocks[thinkingId].startedAt) / 1000
          chatStore.appendThinkingChunk(thinkingId, `✓ ${resultPreview}\n`, elapsedSeconds, 'observing')
        }
        
        // Legacy reasoning block handling
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
        
        // Append to existing content instead of replacing
        const obsReasoningState = useChatStore.getState()
        const message = obsReasoningState.assistantMessages[obsMsgId]
        const existingContent = message?.reasoningBlocks.find(b => b.id === this.currentReasoningBlockId)?.content || ''
        
        const obsContent = existingContent
          ? `${existingContent}\n\n**Итерация ${iteration} - Наблюдение:**\n\n📊 **Результат:** ${result.substring(0, 500)}${result.length > 500 ? '...' : ''}`
          : `**Итерация ${iteration} - Наблюдение:**\n\n📊 **Результат:** ${result.substring(0, 500)}${result.length > 500 ? '...' : ''}`
        
        console.log('[WebSocket] Updating reasoning block with observation content, length:', obsContent.length)
        chatStore.updateReasoningBlock(obsMsgId, this.currentReasoningBlockId, obsContent)
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
        break
      }

      case 'react_complete': {
        // ReAct cycle completed successfully - FALLBACK: complete thinking block
        console.log('[WebSocket] ReAct cycle completed (fallback to thinking):', event.data)
        
        // Collapse all intents when react cycle completes
        const reactCompleteState = useChatStore.getState()
        const reactCompleteWorkflowId = reactCompleteState.activeWorkflowId
        if (reactCompleteWorkflowId) {
          chatStore.collapseAllIntents(reactCompleteWorkflowId)
        }
        
        // Complete thinking block if exists
        const state = useChatStore.getState()
        const thinkingId = state.activeThinkingId
        if (thinkingId) {
          const block = state.thinkingBlocks[thinkingId]
          if (block) {
            const elapsedSeconds = block.status === 'completed' 
              ? block.elapsedSeconds 
              : (Date.now() - block.startedAt) / 1000
            chatStore.completeThinking(thinkingId, true) // Auto-collapse
          }
        }
        
        const completeMsgId = this.currentMessageId || `msg-${Date.now()}`
        
        // Complete reasoning block
        if (this.currentReasoningBlockId) {
          chatStore.completeReasoningBlock(completeMsgId, this.currentReasoningBlockId)
        }
        
        // Add final result
        const result = event.data.result || 'Задача выполнена успешно'
        const trail = event.data.trail || []
        
        const settingsState = useSettingsStore.getState()
        const isQueryMode = settingsState.executionMode === 'query'
        const isAgentMode = settingsState.executionMode === 'agent'
        const activeWorkflowId = state.activeWorkflowId
        
        // For Query and Agent modes, save to workflow.finalResult
        // BUT: Don't overwrite if streaming already provided longer content
        if ((isQueryMode || isAgentMode) && activeWorkflowId) {
          const currentFinalResult = useChatStore.getState().workflows[activeWorkflowId]?.finalResult || ''
          // Only set if we don't have longer content from streaming
          if (result.length > currentFinalResult.length) {
            chatStore.setWorkflowFinalResult(activeWorkflowId, result)
          } else {
            console.log('[WebSocket] react_complete: skipping setFinalResult, streaming provided longer content:', currentFinalResult.length, '>', result.length)
          }
        } else {
          // Create answer block with result (for non-Query/Agent modes or as fallback)
          this.currentAnswerBlockId = `answer-${Date.now()}`
          chatStore.startAnswerBlock(completeMsgId, this.currentAnswerBlockId)
          chatStore.updateAnswerBlock(completeMsgId, this.currentAnswerBlockId, `✅ **Задача выполнена!**\n\n${result}`)
          chatStore.completeAnswerBlock(completeMsgId, this.currentAnswerBlockId)
        }
        
        
        chatStore.setAgentTyping(false)
        chatStore.clearCurrentAction()
        
        
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
        const result = event.data.result || '' // Check if there's any partial result
        
        // Complete thinking block if exists
        const state = useChatStore.getState()
        const thinkingId = state.activeThinkingId
        if (thinkingId) {
          chatStore.completeThinking(thinkingId, false) // Не сворачиваем при ошибке
        }
        
        const settingsState = useSettingsStore.getState()
        const isQueryMode = settingsState.executionMode === 'query'
        const isAgentMode = settingsState.executionMode === 'agent'
        const activeWorkflowId = state.activeWorkflowId
        
        // For Query and Agent modes, save error or partial result to workflow.finalResult
        if ((isQueryMode || isAgentMode) && activeWorkflowId) {
          const errorMessage = `❌ **Ошибка выполнения запроса**\n\n**Причина:** ${reason}\n\n${result ? `**Полученные данные:**\n${result}\n\n` : ''}**Попытки:** ${tried.join(', ') || 'нет'}`
          chatStore.setWorkflowFinalResult(activeWorkflowId, errorMessage)
        } else {
          // Create answer block with error (for non-Query/Agent modes)
          this.currentAnswerBlockId = `answer-${Date.now()}`
          chatStore.startAnswerBlock(failedMsgId, this.currentAnswerBlockId)
          chatStore.updateAnswerBlock(failedMsgId, this.currentAnswerBlockId, `❌ **Задача не выполнена**\n\n**Причина:** ${reason}\n\n${result ? `**Полученные данные:**\n${result}\n\n` : ''}**Попытки:** ${tried.join(', ') || 'нет'}`)
          chatStore.completeAnswerBlock(failedMsgId, this.currentAnswerBlockId)
        }
        
        
        // Don't clear currentAction here - let it stay visible until reasoning blocks complete
        // This ensures the indicator shows what action was being performed even if it failed
        chatStore.setAgentTyping(false)
        // chatStore.clearCurrentAction() - removed to keep action visible
        
        
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

      case 'action_start': {
        // Начало действия агента
        const workflowId = ensureActiveWorkflow()
        if (workflowId && event.data.action_id) {
          chatStore.addAction(workflowId, {
            id: event.data.action_id,
            icon: event.data.icon || 'process',
            status: 'in_progress',
            title: event.data.title || 'Выполнение действия...',
            description: event.data.description,
            timestamp: new Date().toISOString(),
          })
          console.log('[WebSocket] Action started:', event.data.action_id, event.data.title)
        }
        break
      }

      case 'action_complete': {
        // Завершение действия
        const workflowId = ensureActiveWorkflow()
        if (workflowId && event.data.action_id) {
          chatStore.updateAction(workflowId, event.data.action_id, {
            status: 'success',
            details: event.data.details,
          })
          console.log('[WebSocket] Action completed:', event.data.action_id)
        }
        break
      }

      case 'action_error': {
        // Ошибка действия
        const workflowId = ensureActiveWorkflow()
        if (workflowId && event.data.action_id) {
          chatStore.updateAction(workflowId, event.data.action_id, {
            status: 'error',
            error: event.data.error || 'Произошла ошибка',
            details: event.data.details,
          })
          console.log('[WebSocket] Action error:', event.data.action_id, event.data.error)
        }
        break
      }

      case 'action_alternative': {
        // Использована альтернатива
        const workflowId = ensureActiveWorkflow()
        if (workflowId && event.data.action_id) {
          chatStore.updateAction(workflowId, event.data.action_id, {
            status: 'alternative',
            alternativeUsed: event.data.alternative || 'Альтернативный метод',
            details: event.data.details,
          })
          console.log('[WebSocket] Action alternative:', event.data.action_id, event.data.alternative)
        }
        break
      }

      case 'question_request': {
        // Уточняющий вопрос (Plan mode)
        const workflowId = ensureActiveWorkflow()
        if (workflowId) {
          chatStore.addQuestion(workflowId, {
            id: event.data.question_id || `question-${Date.now()}`,
            text: event.data.text || 'У меня есть вопросы:',
            items: event.data.items || [],
            isAnswered: false,
            timestamp: new Date().toISOString(),
          })
          console.log('[WebSocket] Question requested:', event.data.question_id)
        }
        break
      }

      case 'result_summary': {
        // Итоговый результат с метриками
        const workflowId = ensureActiveWorkflow()
        if (workflowId) {
          chatStore.setResultSummary(workflowId, {
            completedTasks: event.data.completed_tasks || [],
            failedTasks: event.data.failed_tasks || [],
            alternativesUsed: event.data.alternatives_used || [],
            duration: event.data.duration,
            tokensUsed: event.data.tokens_used,
          })
          console.log('[WebSocket] Result summary:', workflowId, event.data)
        }
        break
      }
      }
    } catch (error) {
      console.error('[WebSocket] Error handling event:', event.type, error, event.data)
      // Don't throw - we want to continue processing future events
    }
  }

  sendMessage(message: string, fileIds?: string[], openFiles?: any[]): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        const payload: any = {
          type: 'message',
          content: message,
        }
        if (fileIds && fileIds.length > 0) {
          payload.file_ids = fileIds
        }
        if (openFiles && openFiles.length > 0) {
          payload.open_files = openFiles
        }
        this.ws.send(JSON.stringify(payload))
        return true
      } catch (error) {
        console.error('Error sending WebSocket message:', error)
        return false
      }
    }
    return false
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
    } else {
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
