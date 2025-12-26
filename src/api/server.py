"""
FastAPI server with WebSocket support for the multi-agent system.
Provides REST API endpoints and real-time WebSocket communication.
"""

# #region agent log - DEBUG INSTRUMENTATION
import sys
print("[DEBUG][HYP-B] server.py: Starting imports...", flush=True)
# #endregion

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional
from pathlib import Path
import uvicorn
from uuid import uuid4

# #region agent log - DEBUG INSTRUMENTATION
print("[DEBUG][HYP-B] server.py: Standard imports OK, loading app modules...", flush=True)
# #endregion

try:
    from src.utils.config_loader import get_config, reload_config
    # #region agent log
    print("[DEBUG][HYP-C] server.py: config_loader imported OK", flush=True)
    # #endregion
except Exception as e:
    print(f"[DEBUG][HYP-C] server.py: config_loader import FAILED: {e}", flush=True)
    raise

try:
    from src.utils.logging_config import setup_logging, get_logger
    # #region agent log
    print("[DEBUG][HYP-B] server.py: logging_config imported OK", flush=True)
    # #endregion
except Exception as e:
    print(f"[DEBUG][HYP-B] server.py: logging_config import FAILED: {e}", flush=True)
    raise

from src.utils.mcp_loader import get_mcp_manager
from src.api.session_manager import get_session_manager
from src.api.websocket_manager import get_websocket_manager
from src.api.agent_wrapper import AgentWrapper
from src.api.auth_routes import router as auth_router
from src.api.integration_routes import router as integration_router
from src.core.context_manager import ConversationContext
from src.agents.model_factory import get_available_models, get_model_info, MODELS

# #region agent log - DEBUG INSTRUMENTATION
print("[DEBUG][HYP-B] server.py: All imports completed successfully!", flush=True)
# #endregion

# Setup logging and config with error handling
# Allow app to start even if some config is missing (for healthcheck)
# #region agent log - DEBUG INSTRUMENTATION
print("[DEBUG][HYP-C] server.py: Loading config...", flush=True)
# #endregion
try:
    config = get_config()
    setup_logging(config.log_level)
    logger = get_logger(__name__)
    logger.info("Configuration loaded successfully")
    # #region agent log
    print("[DEBUG][HYP-C] server.py: Config loaded OK", flush=True)
    # #endregion
except Exception as e:
    # #region agent log
    print(f"[DEBUG][HYP-C] server.py: Config FAILED: {e}", flush=True)
    # #endregion
    # Fallback config for basic startup
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to load full config: {e}. Using defaults for startup.")
    # Create minimal config for CORS
    class MinimalConfig:
        api_cors_origins = ["*"]
    config = MinimalConfig()

# #region agent log - DEBUG INSTRUMENTATION
print("[DEBUG][HYP-B] server.py: Creating FastAPI app...", flush=True)
# #endregion

# Create FastAPI app
app = FastAPI(
    title="Google Workspace Multi-Agent API",
    description="API for Google Workspace Multi-Agent System",
    version="1.0.0"
)

# #region agent log - DEBUG INSTRUMENTATION
print("[DEBUG][HYP-B] server.py: FastAPI app created OK!", flush=True)
# #endregion

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api_cors_origins if hasattr(config, 'api_cors_origins') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers with error handling
# Allow app to start even if some managers fail (for healthcheck)
try:
    session_manager = get_session_manager()
    ws_manager = get_websocket_manager()
    agent_wrapper = AgentWrapper()
    mcp_manager = get_mcp_manager()
    logger.info("Managers initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize some managers: {e}")
    # Create minimal stubs to prevent crashes
    class StubManager:
        pass
    session_manager = StubManager()
    ws_manager = StubManager()
    agent_wrapper = StubManager()
    mcp_manager = StubManager()

# Include auth routes
app.include_router(auth_router)
# Include integration routes
app.include_router(integration_router)

# Serve static files in production
if hasattr(config, 'is_production') and config.is_production:
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
        
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            """Serve frontend files, fallback to index.html for SPA routing."""
            file_path = frontend_dist / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            # Fallback to index.html for client-side routing
            return FileResponse(frontend_dist / "index.html")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # #region agent log - DEBUG INSTRUMENTATION
    print("[DEBUG][HYP-B] startup_event() called - server is starting!", flush=True)
    # #endregion
    logger.info("Starting up Multi-Agent API...")
    
    # Connect to MCP servers asynchronously (non-blocking)
    # This allows the app to start quickly even if MCP servers are slow to connect
    async def connect_mcp_servers():
        try:
            results = await mcp_manager.connect_all()
            logger.info(f"MCP connection results: {results}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP servers: {e}")
    
    # Start MCP connection in background (non-blocking)
    import asyncio
    asyncio.create_task(connect_mcp_servers())
    
    # #region agent log - DEBUG INSTRUMENTATION
    print("[DEBUG][HYP-B] startup_event() completed - server ready for requests!", flush=True)
    # #endregion
    
    # Cleanup expired sessions periodically
    # (In production, use a background task)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Multi-Agent API...")
    await mcp_manager.disconnect_all()


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint - максимально простой для Railway.
    Возвращает 200 OK сразу после запуска FastAPI, без проверок.
    """
    # #region agent log - DEBUG INSTRUMENTATION
    print("[DEBUG][HYP-A] Healthcheck endpoint called!", flush=True)
    # #endregion
    # Простейший healthcheck - просто подтверждаем, что сервер работает
    # MCP серверы могут подключаться асинхронно, это не критично для healthcheck
    return {
        "status": "healthy",
        "service": "universal-multiagent"
    }


@app.post("/api/chat")
async def send_message(request: Dict[str, Any]):
    """
    Send a message to the agent.
    
    Request body:
    - message: User message
    - session_id: Optional session ID (creates new if not provided)
    - execution_mode: Optional execution mode (instant/approval)
    """
    user_message = request.get("message")
    session_id = request.get("session_id")
    execution_mode = request.get("execution_mode", "instant")
    
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Get or create session
    if session_id:
        context = session_manager.get_session(session_id)
        if not context:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session_id = session_manager.create_session(execution_mode)
        context = session_manager.get_session(session_id)
    
    # Update execution mode if provided
    if execution_mode:
        context.execution_mode = execution_mode
    
    # Process message
    try:
        logger.info(f"Processing message for session {session_id}, context session_id: {getattr(context, 'session_id', 'NOT SET')}")
        result = await agent_wrapper.process_message(
            user_message,
            context,
            session_id
        )
        
        # Update session
        session_manager.update_session(session_id, context)
        
        return {
            "session_id": session_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/create")
async def create_session(request: Dict[str, Any] = {}):
    """
    Create a new session without sending a message.
    
    Request body (optional):
    - execution_mode: Execution mode (instant/approval)
    - model_name: Model identifier (optional)
    """
    execution_mode = request.get("execution_mode", "instant") if request else "instant"
    model_name = request.get("model_name")
    
    session_id = session_manager.create_session(execution_mode)
    context = session_manager.get_session(session_id)
    
    # Set model if provided
    if model_name:
        available_models = get_available_models()
        if model_name in available_models:
            context.model_name = model_name
            session_manager.update_session(session_id, context)
        else:
            logger.warning(f"Model '{model_name}' not available, using default")
    
    return {
        "session_id": session_id,
        "execution_mode": execution_mode,
        "model_name": getattr(context, "model_name", None)
    }


@app.get("/api/chat/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    context = session_manager.get_session(session_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "messages": context.messages,
        "execution_mode": context.execution_mode,
        "model_name": getattr(context, "model_name", None)
    }


@app.post("/api/settings")
async def update_settings(request: Dict[str, Any]):
    """
    Update session settings.
    
    Request body:
    - session_id: Session ID (required)
    - execution_mode: Optional execution mode (instant/approval)
    - model_name: Optional model identifier
    """
    session_id = request.get("session_id")
    execution_mode = request.get("execution_mode")
    model_name = request.get("model_name")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    
    context = session_manager.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if execution_mode:
        context.execution_mode = execution_mode
    
    if model_name:
        # Validate model exists and is available
        available_models = get_available_models()
        if model_name not in available_models:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model_name}' is not available. Available models: {list(available_models.keys())}"
            )
        context.model_name = model_name
    
    session_manager.update_session(session_id, context)
    
    return {
        "session_id": session_id,
        "execution_mode": context.execution_mode,
        "model_name": context.model_name
    }


@app.post("/api/plan/approve")
async def approve_plan(request: Dict[str, Any]):
    """Approve a plan for execution."""
    session_id = request.get("session_id")
    confirmation_id = request.get("confirmation_id")
    
    if not session_id or not confirmation_id:
        raise HTTPException(status_code=400, detail="Session ID and confirmation ID required")
    
    context = session_manager.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        result = await agent_wrapper.approve_plan(
            confirmation_id,
            context,
            session_id
        )
        
        session_manager.update_session(session_id, context)
        
        return {
            "status": "approved",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error approving plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan/reject")
async def reject_plan(request: Dict[str, Any]):
    """Reject a plan."""
    session_id = request.get("session_id")
    confirmation_id = request.get("confirmation_id")
    
    if not session_id or not confirmation_id:
        raise HTTPException(status_code=400, detail="Session ID and confirmation ID required")
    
    context = session_manager.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await agent_wrapper.reject_plan(confirmation_id, context, session_id)
    session_manager.update_session(session_id, context)
    
    return {"status": "rejected"}


@app.get("/api/tools")
async def list_tools():
    """List all available tools."""
    tools = mcp_manager.get_all_tools()
    
    return {
        "tools": [
            {
                "name": name,
                "description": tool.get("description", ""),
                "server": tool.get("server", "")
            }
            for name, tool in tools.items()
        ]
    }


@app.get("/api/models")
async def list_models():
    """
    List all available models with their capabilities.
    
    Returns:
        List of available models with metadata
    """
    config = get_config()
    available_models = get_available_models()
    
    models_list = []
    for model_id, model_config in MODELS.items():
        if model_id in available_models:
            model_info = get_model_info(model_id)
            models_list.append({
                "id": model_id,
                "name": model_info.get("display_name", model_id),
                "provider": model_config["provider"],
                "supports_reasoning": model_config.get("supports_reasoning", False),
                "reasoning_type": model_config.get("reasoning_type"),
                "default": model_id == config.default_model
            })
    
    return {"models": models_list}


@app.post("/api/session/model")
async def set_session_model(request: Dict[str, Any]):
    """
    Set model for a session.
    
    Request body:
    - session_id: Session ID (required)
    - model_name: Model identifier (required, e.g., "gpt-4o", "claude-sonnet-4-5", "o1")
    """
    session_id = request.get("session_id")
    model_name = request.get("model_name")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required")
    
    # Validate model exists and is available
    available_models = get_available_models()
    if model_name not in available_models:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' is not available. Available models: {list(available_models.keys())}"
        )
    
    context = session_manager.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Set model in context
    context.model_name = model_name
    session_manager.update_session(session_id, context)
    
    return {
        "session_id": session_id,
        "model_name": model_name
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication."""
    await ws_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "message":
                # Process user message
                user_message = data.get("content")
                context = session_manager.get_session(session_id)
                
                if not context:
                    context = ConversationContext(session_id)
                    session_manager.update_session(session_id, context)
                
                await agent_wrapper.process_message(
                    user_message,
                    context,
                    session_id
                )
                
                session_manager.update_session(session_id, context)
            
            elif message_type == "approve_plan":
                # Approve plan
                confirmation_id = data.get("confirmation_id")
                context = session_manager.get_session(session_id)
                
                if context:
                    await agent_wrapper.approve_plan(
                        confirmation_id,
                        context,
                        session_id
                    )
                    session_manager.update_session(session_id, context)
            
            elif message_type == "reject_plan":
                # Reject plan
                confirmation_id = data.get("confirmation_id")
                context = session_manager.get_session(session_id)
                
                if context:
                    await agent_wrapper.reject_plan(
                        confirmation_id,
                        context,
                        session_id
                    )
                    session_manager.update_session(session_id, context)
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id)
        logger.info(f"WebSocket disconnected for session {session_id}")


if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug
    )

