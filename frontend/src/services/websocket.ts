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

  connect(sessionId: string): void {
    this.sessionId = sessionId
    this._connect()
  }

  private _connect(): void {
    if (!this.sessionId) {
      console.warn('[WebSocket] Cannot connect: sessionId is null')
      return
    }

    // Close existing connection if any (but only if it's already open or connecting)
    if (this.ws) {
      const state = this.ws.readyState
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
        console.log('[WebSocket] Closing existing connection before creating new one, state:', state)
        this.ws.onclose = null // Prevent reconnect attempt
        this.ws.onerror = null // Prevent error handling
        this.ws.close()
        this.ws = null
        // Small delay to ensure connection is fully closed
        setTimeout(() => this._doConnect(), 50)
        return
      } else if (state === WebSocket.CLOSING) {
        // Wait for closing to complete
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
        
        // Only attempt reconnect if connection was established before (not initial connection failure)
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
    console.log('[WebSocket] Received event:', event.type, event.data)

    switch (event.type) {
      case 'message':
        console.log('[WebSocket] Processing message event, role:', event.data.role)
        // Handle different message roles
        if (event.data.role === 'assistant' || event.data.role === 'system') {
          console.log('[WebSocket] Adding assistant/system message:', event.data.content.substring(0, 50))
          chatStore.addMessage({
            role: event.data.role,
            content: event.data.content,
            timestamp: new Date().toISOString(),
          })
          chatStore.setAgentTyping(false)
          console.log('[WebSocket] Set agent typing to false')
        } else if (event.data.role === 'user') {
          // User messages are already added in handleSend, but if they come from WebSocket
          // (e.g., after reconnection), add them only if not already present
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
        // Start streaming message
        console.log('Starting streaming message:', event.data.message_id)
        chatStore.startStreamingMessage(event.data.message_id, {
          role: event.data.role,
          content: '',
          timestamp: new Date().toISOString(),
        })
        chatStore.setAgentTyping(true)
        break

      case 'message_chunk':
        // Update streaming message with new chunk
        console.log('Updating streaming message:', event.data.message_id, 'chunk length:', event.data.chunk?.length)
        chatStore.updateStreamingMessage(event.data.message_id, event.data.content)
        break

      case 'message_complete':
        // Complete streaming message
        console.log('Completing streaming message:', event.data.message_id)
        chatStore.completeStreamingMessage(event.data.message_id, event.data.content)
        chatStore.setAgentTyping(false)
        break

      case 'thinking':
        console.log('[WebSocket] Thinking event:', event.data)
        chatStore.setAgentTyping(true)
        const thinkingMessage = event.data.message || event.data.step || 'Thinking...'
        console.log('[WebSocket] Adding reasoning step (thought):', thinkingMessage)
        chatStore.addReasoningStep({
          type: 'thought',
          content: thinkingMessage,
          timestamp: new Date().toISOString(),
          data: event.data,
        })
        break

      case 'tool_call':
        console.log('[WebSocket] Tool call event:', event.data)
        const toolName = event.data.tool_name || event.data.name || 'Unknown tool'
        const toolArgs = event.data.arguments || event.data.args || {}
        // Make tool call description more compact
        let toolCallContent = toolName
        if (Object.keys(toolArgs).length > 0) {
          // Show only key parameter names, not full values
          const paramKeys = Object.keys(toolArgs).slice(0, 3)
          toolCallContent += ` (${paramKeys.join(', ')}${Object.keys(toolArgs).length > 3 ? '...' : ''})`
        }
        console.log('[WebSocket] Adding reasoning step (tool_call):', toolCallContent)
        chatStore.addReasoningStep({
          type: 'tool_call',
          content: toolCallContent,
          timestamp: new Date().toISOString(),
          data: event.data,
        })
        break

      case 'tool_result':
        console.log('[WebSocket] Tool result event:', event.data)
        const resultContent = event.data.result || event.data.content || 'Выполнение завершено'
        // Keep result text compact - don't add "Результат: " prefix, ThinkingBlock will handle formatting
        const resultText = typeof resultContent === 'string' ? resultContent : JSON.stringify(resultContent)
        // Truncate very long results
        const compactResult = resultText.length > 1000 
          ? resultText.substring(0, 1000) + '\n\n... (результат обрезан) ...'
          : resultText
        console.log('[WebSocket] Adding reasoning step (tool_result):', compactResult.substring(0, 100))
        chatStore.addReasoningStep({
          type: 'tool_result',
          content: compactResult,
          timestamp: new Date().toISOString(),
          data: event.data,
        })
        break

      case 'plan_request':
        // Handle plan approval request
        break

      case 'error':
        chatStore.addMessage({
          role: 'system',
          content: `Error: ${event.data.message}`,
          timestamp: new Date().toISOString(),
        })
        chatStore.setAgentTyping(false)
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
    }
  }

  rejectPlan(confirmationId: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'reject_plan',
        confirmation_id: confirmationId,
      }))
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

export const wsClient = new WebSocketClient()

