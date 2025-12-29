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

    const wsUrl = `ws://localhost:8000/ws/${this.sessionId}`
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
          
          // #region agent log - WebSocket events log
          // Логируем все события в отдельный файл для анализа порядка
          const eventLog = {
            timestamp: Date.now(),
            eventType: data.type,
            eventData: {
              // Логируем основные поля события
              message_id: data.data?.message_id || null,
              content: data.data?.content ? (typeof data.data.content === 'string' ? data.data.content.substring(0, 200) : String(data.data.content).substring(0, 200)) : null,
              contentLength: data.data?.content ? (typeof data.data.content === 'string' ? data.data.content.length : String(data.data.content).length) : null,
              message: data.data?.message ? (typeof data.data.message === 'string' ? data.data.message.substring(0, 200) : String(data.data.message).substring(0, 200)) : null,
              messageLength: data.data?.message ? (typeof data.data.message === 'string' ? data.data.message.length : String(data.data.message).length) : null,
              step: data.data?.step || null,
              tool_name: data.data?.tool_name || data.data?.name || null,
              arguments: data.data?.arguments || data.data?.args || null,
              result: data.data?.result ? (typeof data.data.result === 'string' ? data.data.result.substring(0, 200) : String(data.data.result).substring(0, 200)) : null,
              stop_reason: data.data?.stop_reason || null,
              role: data.data?.role || null,
              // Полный объект data для детального анализа (ограничиваем размер)
              fullData: JSON.stringify(data.data).substring(0, 1000),
            },
            rawEvent: JSON.stringify(data).substring(0, 2000), // Полное событие (ограничено)
          }
          
          // Записываем в отдельный файл лога WebSocket событий
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              location: 'websocket.ts:onmessage',
              message: 'WebSocket event received from backend',
              data: eventLog,
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'websocket-events',
              hypothesisId: 'EVENTS'
            })
          }).catch(() => {})
          // #endregion
          
          this.handleEvent(data)
        } catch (error) {
          console.error('[WebSocket] Error handling message:', error, event.data)
          
          // #region agent log - Error logging
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              location: 'websocket.ts:onmessage-error',
              message: 'Error parsing WebSocket event',
              data: {
                error: String(error),
                rawData: String(event.data).substring(0, 500),
              },
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'websocket-events',
              hypothesisId: 'EVENTS'
            })
          }).catch(() => {})
          // #endregion
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
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:handleEvent-message-user',message:'WebSocket user message event received',data:{eventContent:event.data.content,eventContentLength:event.data.content.length,lastMessageContent:lastMessage?.content,lastMessageRole:lastMessage?.role,willAdd:!lastMessage||lastMessage.content!==event.data.content||lastMessage.role!=='user',allMessagesCount:allMessages.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
          // #endregion
          if (!lastMessage || lastMessage.content !== event.data.content || lastMessage.role !== 'user') {
            chatStore.addMessage({
              role: 'user',
              content: event.data.content,
              timestamp: new Date().toISOString(),
            })
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:handleEvent-message-user',message:'ADDED user message from WebSocket',data:{eventContent:event.data.content},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
            // #endregion
          } else {
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:handleEvent-message-user',message:'SKIPPED duplicate user message from WebSocket',data:{eventContent:event.data.content,lastMessageContent:lastMessage.content},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
            // #endregion
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
        // Reasoning/thinking event
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-entry',message:'THINKING event received',data:{hasCurrentMessageId:!!this.currentMessageId,currentMessageId:this.currentMessageId,hasCurrentReasoningBlockId:!!this.currentReasoningBlockId,currentReasoningBlockId:this.currentReasoningBlockId,hasCurrentAnswerBlockId:!!this.currentAnswerBlockId,currentAnswerBlockId:this.currentAnswerBlockId,messageLength:event.data.message?.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,D'})}).catch(()=>{});
        // #endregion
        chatStore.setAgentTyping(true)
        const thinkingMessage = event.data.message || event.data.step || 'Thinking...'
        
        // Get or create current message ID
        if (!this.currentMessageId) {
          this.currentMessageId = `msg-${Date.now()}`
        }
        const thinkingMsgId = this.currentMessageId
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-before-update',message:'Before reasoning block update',data:{thinkingMsgId,hasReasoningBlockId:!!this.currentReasoningBlockId,reasoningBlockId:this.currentReasoningBlockId,thinkingMessageLength:thinkingMessage.length,assistantMessagesCount:Object.keys(chatStore.assistantMessages).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B,E'})}).catch(()=>{});
        // #endregion
        
        // #region agent log
        const beforeThinkingState = useChatStore.getState()
        const currentMessage = beforeThinkingState.assistantMessages[thinkingMsgId]
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-before-logic',message:'Before reasoning block logic',data:{thinkingMsgId,hasCurrentReasoningBlockId:!!this.currentReasoningBlockId,currentReasoningBlockId:this.currentReasoningBlockId,hasCurrentAnswerBlockId:!!this.currentAnswerBlockId,currentAnswerBlockId:this.currentAnswerBlockId,existingReasoningBlocksCount:currentMessage?.reasoningBlocks.length||0,existingAnswerBlocksCount:currentMessage?.answerBlocks.length||0,lastReasoningIsStreaming:currentMessage?.reasoningBlocks[currentMessage?.reasoningBlocks.length-1]?.isStreaming,lastAnswerIsStreaming:currentMessage?.answerBlocks[currentMessage?.answerBlocks.length-1]?.isStreaming},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'A,B,C,D'})}).catch(()=>{});
        // #endregion
        
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
          shouldCreateNewReasoningBlock = true
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-new-cycle',message:'Starting new reasoning cycle after answer',data:{thinkingMsgId,completedAnswerBlockId:this.currentAnswerBlockId},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'C'})}).catch(()=>{});
          // #endregion
        }
        // Case 2: If we have a reasoning block, check if it's still streaming
        else if (this.currentReasoningBlockId) {
          const currentMessage = useChatStore.getState().assistantMessages[thinkingMsgId]
          const currentReasoningBlock = currentMessage?.reasoningBlocks.find((b: any) => b.id === this.currentReasoningBlockId)
          
          if (currentReasoningBlock) {
            if (currentReasoningBlock.isStreaming) {
              // Reasoning block is still streaming - this is a CONTINUATION of the same block
              // We should UPDATE it, not create a new one
              shouldCreateNewReasoningBlock = false
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-continue-existing',message:'Continuing existing reasoning block',data:{thinkingMsgId,reasoningBlockId:this.currentReasoningBlockId,isStreaming:currentReasoningBlock.isStreaming},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
            } else {
              // Reasoning block is completed - this is a NEW reasoning block
              shouldCreateNewReasoningBlock = true
              this.currentReasoningBlockId = null
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-old-completed',message:'Previous reasoning block completed, creating new one',data:{thinkingMsgId,oldReasoningBlockId:this.currentReasoningBlockId},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
            }
          } else {
            // Reasoning block not found in store - create new one
            const missingReasoningBlockId = this.currentReasoningBlockId
            shouldCreateNewReasoningBlock = true
            this.currentReasoningBlockId = null
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-block-not-found',message:'Reasoning block not found in store, creating new',data:{thinkingMsgId,missingReasoningBlockId},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
            // #endregion
          }
        }
        // Case 3: No reasoning block exists - create new one
        else {
          shouldCreateNewReasoningBlock = true
        }
        
        // Create new reasoning block if needed
        if (shouldCreateNewReasoningBlock) {
          this.currentReasoningBlockId = `reasoning-${Date.now()}`
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-start-block',message:'Starting new reasoning block',data:{thinkingMsgId,reasoningBlockId:this.currentReasoningBlockId,reasoningBlockTimestamp:new Date().toISOString()},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A,C'})}).catch(()=>{});
          // #endregion
          chatStore.startReasoningBlock(thinkingMsgId, this.currentReasoningBlockId)
        }
        
        // Update reasoning block content (replace, not append - backend sends accumulated content)
        // At this point, currentReasoningBlockId must be set (either existing or newly created)
        if (!this.currentReasoningBlockId) {
          console.error('[WebSocket] ERROR: currentReasoningBlockId is null when trying to update reasoning block')
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-error-no-block-id',message:'ERROR: currentReasoningBlockId is null',data:{thinkingMsgId,contentLength:thinkingMessage.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'A'})}).catch(()=>{});
          // #endregion
          break
        }
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-before-update-call',message:'Before updateReasoningBlock call',data:{thinkingMsgId,reasoningBlockId:this.currentReasoningBlockId,contentLength:thinkingMessage.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'B'})}).catch(()=>{});
        // #endregion
        chatStore.updateReasoningBlock(thinkingMsgId, this.currentReasoningBlockId, thinkingMessage)
        addDebugChunkIfEnabled(thinkingMsgId, 'thinking', thinkingMessage, event.data)
        // #region agent log
        const afterUpdateState = useChatStore.getState()
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:thinking-after-update',message:'After reasoning block update',data:{thinkingMsgId,reasoningBlockId:this.currentReasoningBlockId,hasMessage:!!afterUpdateState.assistantMessages[thinkingMsgId],reasoningBlocksCount:afterUpdateState.assistantMessages[thinkingMsgId]?.reasoningBlocks.length||0,lastReasoningContentLength:afterUpdateState.assistantMessages[thinkingMsgId]?.reasoningBlocks[afterUpdateState.assistantMessages[thinkingMsgId]?.reasoningBlocks.length-1]?.content.length||0,lastReasoningIsStreaming:afterUpdateState.assistantMessages[thinkingMsgId]?.reasoningBlocks[afterUpdateState.assistantMessages[thinkingMsgId]?.reasoningBlocks.length-1]?.isStreaming},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B,E'})}).catch(()=>{});
        // #endregion
        console.log('[WebSocket] Updated reasoning block:', this.currentReasoningBlockId, 'content length:', thinkingMessage.length)
        break

      case 'message_chunk':
        // Streaming answer content
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-entry',message:'MESSAGE_CHUNK event received',data:{hasCurrentMessageId:!!this.currentMessageId,currentMessageId:this.currentMessageId,eventMessageId:event.data.message_id,hasCurrentReasoningBlockId:!!this.currentReasoningBlockId,currentReasoningBlockId:this.currentReasoningBlockId,hasCurrentAnswerBlockId:!!this.currentAnswerBlockId,currentAnswerBlockId:this.currentAnswerBlockId,chunkLength:event.data.content?.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C,F'})}).catch(()=>{});
        // #endregion
        const chunkContent = event.data.content || ''
        
        // CRITICAL FIX: If event.data.message_id exists and differs from currentMessageId,
        // and we have a reasoning block, we need to move the reasoning block to the new message
        const eventMessageId = event.data.message_id
        let chunkMsgId: string
        
        if (!this.currentMessageId) {
          // No current message, use event message_id or create new
          chunkMsgId = eventMessageId || `msg-${Date.now()}`
          this.currentMessageId = chunkMsgId
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-created-messageid',message:'Created new messageId from message_chunk',data:{newMessageId:chunkMsgId,eventMessageId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
          // #endregion
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
              
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-copied-reasoning',message:'Copied reasoning blocks to new message',data:{oldMessageId,newMessageId:chunkMsgId,reasoningBlocksCount:reasoningBlocksToCopy.length,reasoningBlockIds:reasoningBlocksToCopy.map((b:any)=>b.id),currentReasoningBlockId:this.currentReasoningBlockId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
              // #endregion
            }
          } else if (this.currentReasoningBlockId && oldMessage) {
            // Fallback: copy single reasoning block if currentReasoningBlockId is set
            const reasoningBlock = oldMessage.reasoningBlocks.find((b: any) => b.id === this.currentReasoningBlockId)
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
                // #region agent log
                fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-copied-reasoning',message:'Copied reasoning block to new message with preserved timestamp',data:{oldMessageId,newMessageId:chunkMsgId,reasoningBlockId:this.currentReasoningBlockId,reasoningContentLength:reasoningBlock.content.length,originalTimestamp:reasoningBlock.timestamp},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                // #endregion
              }
            }
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-switched-messageid',message:'Switched messageId for message_chunk',data:{oldMessageId,newMessageId:chunkMsgId,eventMessageId,hasReasoningBlock:!!this.currentReasoningBlockId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
          // #endregion
        } else {
          // Use existing currentMessageId
          chunkMsgId = this.currentMessageId as string
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-using-existing',message:'Using existing messageId for message_chunk',data:{existingMessageId:chunkMsgId,eventMessageId,messageIdsMatch:chunkMsgId===eventMessageId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
          // #endregion
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
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-complete-reasoning',message:'Completing reasoning block before answer',data:{chunkMsgId,reasoningBlockId:this.currentReasoningBlockId,reasoningIsStreaming:reasoningBlock.isStreaming},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C,F'})}).catch(()=>{});
              // #endregion
              chatStore.completeReasoningBlock(chunkMsgId, this.currentReasoningBlockId)
            }
          }
          this.currentReasoningBlockId = null
        }
        
        // Get or create answer block
        if (!this.currentAnswerBlockId) {
          this.currentAnswerBlockId = `answer-${Date.now()}`
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-start-answer',message:'Starting new answer block',data:{chunkMsgId,answerBlockId:this.currentAnswerBlockId,answerBlockTimestamp:new Date().toISOString(),hasActiveReasoning:!!this.currentReasoningBlockId},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'B,D'})}).catch(()=>{});
          // #endregion
          chatStore.startAnswerBlock(chunkMsgId, this.currentAnswerBlockId)
        }
        
        // Update answer block content (replace, not append - backend sends accumulated content)
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-before-update',message:'Before answer block update',data:{chunkMsgId,answerBlockId:this.currentAnswerBlockId,contentLength:chunkContent.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        chatStore.updateAnswerBlock(chunkMsgId, this.currentAnswerBlockId, chunkContent)
        addDebugChunkIfEnabled(chunkMsgId, 'message_chunk', chunkContent, { ...event.data, chunk: event.data.chunk })
        // #region agent log
        const afterAnswerUpdate = useChatStore.getState()
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:message_chunk-after-update',message:'After answer block update',data:{chunkMsgId,answerBlockId:this.currentAnswerBlockId,hasMessage:!!afterAnswerUpdate.assistantMessages[chunkMsgId],answerBlocksCount:afterAnswerUpdate.assistantMessages[chunkMsgId]?.answerBlocks.length||0,lastAnswerContentLength:afterAnswerUpdate.assistantMessages[chunkMsgId]?.answerBlocks[afterAnswerUpdate.assistantMessages[chunkMsgId]?.answerBlocks.length-1]?.content.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C,E'})}).catch(()=>{});
        // #endregion
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
        // Accumulate thinking during plan generation
        useChatStore.getState().updatePlanThinking(event.data.content || '')
        console.log('[WebSocket] Plan thinking chunk:', event.data.content?.substring(0, 50))
        break

      case 'plan_generated':
        // Save plan to chatStore - use getState() to get fresh state after set
        useChatStore.getState().setWorkflowPlan(
          event.data.plan || '',
          event.data.steps || [],
          event.data.confirmation_id || null
        )
        // #region agent log
        const stateAfterPlan = useChatStore.getState()
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:plan_generated-verify',message:'Verify plan set',data:{hasPlan:!!stateAfterPlan.workflowPlan,stepsCount:stateAfterPlan.workflowPlan?.steps.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'verify',hypothesisId:'VERIFY'})}).catch(()=>{});
        // #endregion
        console.log('[WebSocket] Plan generated:', event.data.plan)
        break

      case 'awaiting_confirmation':
        // Show confirmation buttons - use getState() to get fresh state
        useChatStore.getState().setAwaitingConfirmation(true)
        console.log('[WebSocket] Awaiting confirmation')
        break

      case 'step_start':
        // Start a new workflow step - use getState() to get fresh state after set
        // #region agent log
        const stateBeforeStepStart = useChatStore.getState()
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:step_start',message:'step_start event received',data:{step:event.data.step,title:event.data.title,hasWorkflowPlan:!!stateBeforeStepStart.workflowPlan,workflowStepsCount:Object.keys(stateBeforeStepStart.workflowSteps).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'STEP'})}).catch(()=>{});
        // #endregion
        useChatStore.getState().startWorkflowStep(event.data.step, event.data.title || `Step ${event.data.step}`)
        // #region agent log
        const stateAfterStepStart = useChatStore.getState()
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'websocket.ts:step_start-after',message:'After startWorkflowStep',data:{step:event.data.step,workflowStepsCount:Object.keys(stateAfterStepStart.workflowSteps).length,currentWorkflowStep:stateAfterStepStart.currentWorkflowStep},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'STEP'})}).catch(()=>{});
        // #endregion
        console.log('[WebSocket] Step started:', event.data.step, event.data.title)
        break

      case 'thinking_chunk':
        // Add thinking chunk to current step (streaming) - use getState() to get fresh state
        const currentStateForThinking = useChatStore.getState()
        const currentStep = currentStateForThinking.currentWorkflowStep
        if (currentStep !== null) {
          currentStateForThinking.updateStepThinking(currentStep, event.data.content || '')
        }
        break

      case 'response_chunk':
        // Add response chunk to current step (streaming) - use getState() to get fresh state
        const currentStateForResponse = useChatStore.getState()
        const currentStepForResponse = currentStateForResponse.currentWorkflowStep
        if (currentStepForResponse !== null) {
          currentStateForResponse.updateStepResponse(currentStepForResponse, event.data.content || '')
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

      case 'workflow_complete':
        // Complete the entire workflow - use getState() to get fresh state
        const finalState = useChatStore.getState()
        finalState.completeWorkflow()
        finalState.setAgentTyping(false)
        console.log('[WebSocket] Workflow completed')
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
    }
  }

  sendMessage(message: string): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({
          type: 'message',
          content: message,
        }))
        return true
      } catch (error) {
        console.error('Error sending WebSocket message:', error)
        return false
      }
    }
    return false
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
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
