"""
FastAPI server with WebSocket support for the multi-agent system.
Provides REST API endpoints and real-time WebSocket communication.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional
from pathlib import Path
import uvicorn
from uuid import uuid4

from src.utils.config_loader import get_config, reload_config
from src.utils.logging_config import setup_logging, get_logger
from src.utils.mcp_loader import get_mcp_manager
from src.api.session_manager import get_session_manager
from src.api.websocket_manager import get_websocket_manager
from src.api.agent_wrapper import AgentWrapper
from src.api.auth_routes import router as auth_router
from src.api.integration_routes import router as integration_router
from src.core.context_manager import ConversationContext
from src.agents.model_factory import get_available_models, get_model_info, MODELS

# Setup logging and config with error handling
# Allow app to start even if some config is missing (for healthcheck)
try:
    config = get_config()
    setup_logging(config.log_level)
    logger = get_logger(__name__)
    logger.info("Configuration loaded successfully")
    # #region agent log
    try:
        import json
        import time
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location": "server.py:32", "message": "Config loaded successfully at startup", "data": {"has_anthropic": bool(config.anthropic_api_key and config.anthropic_api_key.strip()), "has_openai": bool(config.openai_api_key and config.openai_api_key.strip())}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "O"}) + "\n")
    except: pass
    print(f"[DEBUG] Config loaded - Anthropic: {'set' if config.anthropic_api_key and config.anthropic_api_key.strip() else 'missing'}, OpenAI: {'set' if config.openai_api_key and config.openai_api_key.strip() else 'missing'}", flush=True)
    # #endregion
except Exception as e:
    # Fallback config for basic startup
    import logging
    import traceback
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to load full config: {e}. Using defaults for startup.")
    logger.error(f"Config error traceback: {traceback.format_exc()}")
    print(f"[DEBUG] Config load failed: {e}", flush=True)
    # #region agent log
    try:
        import json
        import time
        import traceback
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location": "server.py:48", "message": "Config load failed at startup", "data": {"error": str(e), "traceback": traceback.format_exc()}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "P"}) + "\n")
    except: pass
    # #endregion
    # Create minimal config for CORS
    class MinimalConfig:
        api_cors_origins = ["*"]
        is_production = True  # Assume production if config fails
        anthropic_api_key = None
        openai_api_key = None
        log_level = "INFO"
    config = MinimalConfig()

# Create FastAPI app
app = FastAPI(
    title="Google Workspace Multi-Agent API",
    description="API for Google Workspace Multi-Agent System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
session_manager = get_session_manager()
ws_manager = get_websocket_manager()
agent_wrapper = AgentWrapper()
mcp_manager = get_mcp_manager()

# Include auth routes
app.include_router(auth_router)
# Include integration routes
app.include_router(integration_router)

# Serve static files in production
if config.is_production:
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
    logger.info("Starting up Multi-Agent API...")
    
    # Connect to MCP servers
    try:
        results = await mcp_manager.connect_all()
        logger.info(f"MCP connection results: {results}")
    except Exception as e:
        logger.error(f"Failed to connect to MCP servers: {e}")
    
    # Cleanup expired sessions periodically
    # (In production, use a background task)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Multi-Agent API...")
    await mcp_manager.disconnect_all()


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    mcp_health = await mcp_manager.health_check()
    
    return {
        "status": "healthy",
        "mcp_servers": mcp_health
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
    # #region agent log
    try:
        import json
        import time
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location": "server.py:316", "message": "/api/models endpoint called", "data": {}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "K"}) + "\n")
    except: pass
    logger.info("[DEBUG] /api/models endpoint called")
    print("[DEBUG] /api/models endpoint called", flush=True)
    # #endregion
    
    try:
        config = get_config()
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location": "server.py:325", "message": "Before get_available_models call", "data": {"config_loaded": True}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "L"}) + "\n")
        except: pass
        logger.info("[DEBUG] Config loaded, calling get_available_models()")
        print("[DEBUG] Config loaded, calling get_available_models()", flush=True)
        # #endregion
        
        available_models = get_available_models()
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location": "server.py:328", "message": "After get_available_models call", "data": {"available_count": len(available_models), "available_ids": list(available_models.keys())}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "M"}) + "\n")
        except: pass
        # #endregion
        
        # Log for debugging
        logger.info(f"[DEBUG] Available models count: {len(available_models)}, IDs: {list(available_models.keys())}")
        logger.info(f"[DEBUG] API keys status: Anthropic={'set' if config.anthropic_api_key and config.anthropic_api_key.strip() else 'missing'}, OpenAI={'set' if config.openai_api_key and config.openai_api_key.strip() else 'missing'}")
        logger.info(f"[DEBUG] Anthropic key length: {len(config.anthropic_api_key) if config.anthropic_api_key else 0}, OpenAI key length: {len(config.openai_api_key) if config.openai_api_key else 0}")
        print(f"[DEBUG] Available models count: {len(available_models)}, IDs: {list(available_models.keys())}", flush=True)
        print(f"[DEBUG] API keys - Anthropic: {'set' if config.anthropic_api_key and config.anthropic_api_key.strip() else 'missing'} (len={len(config.anthropic_api_key) if config.anthropic_api_key else 0}), OpenAI: {'set' if config.openai_api_key and config.openai_api_key.strip() else 'missing'} (len={len(config.openai_api_key) if config.openai_api_key else 0})", flush=True)
        
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
        
        logger.info(f"[DEBUG] Returning {len(models_list)} models to client: {[m['id'] for m in models_list]}")
        print(f"[DEBUG] Returning {len(models_list)} models to client: {[m['id'] for m in models_list]}", flush=True)
        return {"models": models_list}
    except Exception as e:
        logger.error(f"[DEBUG] Error listing models: {e}", exc_info=True)
        # #region agent log
        try:
            import json
            import time
            import traceback
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location": "server.py:348", "message": "Exception in list_models", "data": {"error": str(e), "traceback": traceback.format_exc()}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "N"}) + "\n")
        except: pass
        # #endregion
        # Return empty list instead of failing
        return {"models": []}


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

