"""
FastAPI server with WebSocket support for the multi-agent system.
Provides REST API endpoints and real-time WebSocket communication.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional
from pathlib import Path
import uvicorn
from uuid import uuid4
import base64
import io
import json
import time
import asyncio
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

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
except Exception as e:
    # Fallback config for basic startup
    import logging
    import traceback
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to load full config: {e}. Using defaults for startup.")
    logger.error(f"Config error traceback: {traceback.format_exc()}")
    print(f"[DEBUG] Config load failed: {e}", flush=True)
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

# Request logging middleware for debugging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        return response

app.add_middleware(RequestLoggingMiddleware)

# Initialize managers with error handling
# Allow app to start even if some managers fail (for healthcheck)
try:
    session_manager = get_session_manager()
    ws_manager = get_websocket_manager()
    agent_wrapper = AgentWrapper()
    mcp_manager = get_mcp_manager()
    logger.info("Managers initialized successfully")
except Exception as e:
    import traceback
    logger.error(f"Failed to initialize some managers: {e}")
    logger.error(f"Manager init error traceback: {traceback.format_exc()}")
    print(f"[DEBUG] Manager init failed: {e}", flush=True)
    # Create minimal stubs to prevent crashes
    class StubManager:
        async def connect_all(self):
            return {}
        def get_all_tools(self):
            return {}
        async def disconnect_all(self):
            pass
    session_manager = StubManager()
    ws_manager = StubManager()
    agent_wrapper = StubManager()
    mcp_manager = StubManager()

# Include auth routes
app.include_router(auth_router)
# Include integration routes
app.include_router(integration_router)

# Log registered routes for debugging
print(f"[DEBUG] Integration router registered with {len(list(integration_router.routes))} routes", flush=True)

# Serve static files in production
if config.is_production:
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
        
        # Serve favicon explicitly
        @app.get("/favicon.svg")
        async def serve_favicon():
            favicon_path = frontend_dist / "favicon.svg"
            if favicon_path.exists():
                return FileResponse(favicon_path, media_type="image/svg+xml")
            return JSONResponse({"error": "Favicon not found"}, status_code=404)
        
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            """
Serve frontend files, fallback to index.html for SPA routing."""
            file_path = frontend_dist / full_path
            if file_path.exists() and file_path.is_file():
                # Set correct MIME type for common files
                media_type = None
                if full_path.endswith('.svg'):
                    media_type = "image/svg+xml"
                elif full_path.endswith('.js'):
                    media_type = "application/javascript"
                elif full_path.endswith('.css'):
                    media_type = "text/css"
                return FileResponse(file_path, media_type=media_type)
            # Fallback to index.html for client-side routing
            return FileResponse(frontend_dist / "index.html")


@app.on_event("startup")
async def startup_event():
    """
Initialize services on startup."""
    # Generate unique server instance ID for this startup
    import uuid
    import time
    server_instance_id = str(uuid.uuid4())[:8]
    startup_timestamp = int(time.time() * 1000)
    
    # Log unique server startup identifier
    logger.info(f"🚀 SERVER STARTUP - Instance ID: {server_instance_id}, Timestamp: {startup_timestamp}")
    print(f"[🚀 SERVER STARTUP] Instance ID: {server_instance_id}, Timestamp: {startup_timestamp}", flush=True)
    
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
    """
Cleanup on shutdown."""
    logger.info("Shutting down Multi-Agent API...")
    await mcp_manager.disconnect_all()


@app.get("/api/health")
async def health_check():
    """
Health check endpoint."""
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
    - file_ids: Optional list of file IDs to attach to the message
    - open_files: Optional list of currently open files in workspace panel
    """
    
    user_message = request.get("message", "")
    session_id = request.get("session_id")
    execution_mode = request.get("execution_mode", "agent")
    file_ids = request.get("file_ids", [])
    open_files = request.get("open_files", [])
    
    if not user_message and not file_ids:
        raise HTTPException(status_code=400, detail="Message or file is required")
    
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
    
    # Process message with file attachments
    try:
        logger.info(f"Processing message for session {session_id}, context session_id: {getattr(context, 'session_id', 'NOT SET')}, file_ids: {file_ids}, open_files: {len(open_files)}")
        result = await agent_wrapper.process_message(
            user_message,
            context,
            session_id,
            file_ids=file_ids,
            open_files=open_files
        )
        
        # Update session
        session_manager.update_session(session_id, context)
        
        return {
            "session_id": session_id,
            "result": result
        }
    except Exception as e:
        import traceback
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
    """
Get conversation history for a session."""
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
    """
Approve a plan for execution."""
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
    """
Reject a plan."""
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


@app.post("/api/assistance/resolve")
async def resolve_user_assistance(request: Dict[str, Any]):
    """
    Resolve a user assistance request with user's selection.
    
    Request body:
    {
        "session_id": "...",
        "assistance_id": "...",
        "user_response": "1" or "первый" or "Тест2" etc.
    }
    """
    
    session_id = request.get("session_id")
    assistance_id = request.get("assistance_id")
    user_response = request.get("user_response")
    
    
    if not session_id or not assistance_id or not user_response:
        raise HTTPException(status_code=400, detail="Session ID, assistance ID, and user response required")
    
    
    context = session_manager.get_session(session_id)
    
    
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        
        result = await agent_wrapper.resolve_user_assistance(
            assistance_id,
            user_response,
            context,
            session_id
        )
        
        
        
        session_manager.update_session(session_id, context)
        
        
        return result
    except Exception as e:
        logger.error(f"Error resolving user assistance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/plan/update")
async def update_plan(request: Dict[str, Any]):
    """
Update a pending plan."""
    session_id = request.get("session_id")
    confirmation_id = request.get("confirmation_id")
    updated_plan = request.get("updated_plan")

    if not session_id or not confirmation_id or not updated_plan:
        raise HTTPException(status_code=400, detail="Session ID, confirmation ID, and updated plan required")

    context = session_manager.get_session(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await agent_wrapper.update_plan(
            confirmation_id,
            updated_plan,
            context,
            session_id
        )
        session_manager.update_session(session_id, context)
        return {"status": "updated", "result": result}
    except Exception as e:
        logger.error(f"Error updating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools")
async def list_tools():
    """
List all available tools."""
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
    try:
        config = get_config()
        available_models = get_available_models()
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
        # Return empty list instead of failing
        return {"models": []}


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Upload and process file (image or PDF).
    
    Supported file types:
    - Images: image/* (JPEG, PNG, GIF, WEBP, etc.)
    - PDF: application/pdf
    - Word documents: application/vnd.openxmlformats-officedocument.wordprocessingml.document (.docx)
    
    Returns file_id that can be used when sending messages.
    """
    logger.info(f"Upload endpoint called: filename={file.filename}, session_id={session_id}")
    try:
        file_type = file.content_type
        if not file_type:
            raise HTTPException(status_code=400, detail="Could not determine file type")
        
        # Read file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Maximum file size: 20MB
        max_size = 20 * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size: 20MB")
        
        file_id = str(uuid4())
        result = {
            "file_id": file_id,
            "filename": file.filename,
            "type": file_type,
            "size": len(content)
        }
        
        # Get or create session
        context = session_manager.get_session(session_id)
        if not context:
            context = ConversationContext(session_id)
            session_manager.update_session(session_id, context)
        
        # Process based on file type
        if file_type.startswith("image/"):
            # For images - encode to base64
            result["data"] = base64.b64encode(content).decode('utf-8')
            result["media_type"] = file_type
            
            # Store in context
            context.add_file(file_id, {
                "filename": file.filename,
                "type": file_type,
                "media_type": file_type,
                "data": result["data"],
                "size": len(content)
            })
            
        elif file_type == "application/pdf":
            # For PDF - extract text
            if PyPDF2 is None:
                raise HTTPException(
                    status_code=500, 
                    detail="PDF processing not available. Please install PyPDF2."
                )
            
            try:
                pdf_file = io.BytesIO(content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                
                # Extract text from all pages
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                    except Exception as e:
                        logger.warning(f"Error extracting text from PDF page {page_num + 1}: {e}")
                        continue
                
                if not text.strip():
                    raise HTTPException(
                        status_code=400, 
                        detail="Could not extract text from PDF. The PDF might be image-based or encrypted."
                    )
                
                result["text"] = text.strip()
                
                # Store in context
                context.add_file(file_id, {
                    "filename": file.filename,
                    "type": file_type,
                    "text": result["text"],
                    "size": len(content),
                    "pages": len(pdf_reader.pages)
                })
                
            except Exception as e:
                logger.error(f"Error processing PDF: {e}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Error processing PDF: {str(e)}"
                )
        
        elif file_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                          "application/msword"):
            # For .docx and .doc files
            if not DOCX_AVAILABLE:
                raise HTTPException(
                    status_code=500,
                    detail="Word document processing not available. Please install python-docx."
                )
            
            try:
                # For .docx
                if file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    doc_file = io.BytesIO(content)
                    doc = Document(doc_file)
                    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                else:
                    # For .doc (old format) - not directly supported by python-docx
                    raise HTTPException(
                        status_code=400,
                        detail="Old .doc format is not supported. Please convert to .docx"
                    )
                
                if not text.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract text from Word document."
                    )
                
                result["text"] = text.strip()
                
                # Store in context
                context.add_file(file_id, {
                    "filename": file.filename,
                    "type": file_type,
                    "text": result["text"],
                    "size": len(content)
                })
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing Word document: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing Word document: {str(e)}"
                )
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_type}. Supported types: image/*, application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        
        # Update session
        session_manager.update_session(session_id, context)
        logger.info(f"File uploaded successfully: {file.filename} ({file_type}, {len(content)} bytes) for session {session_id}")
        
        return result
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


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
    """
WebSocket endpoint for real-time communication."""
    
    await ws_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            try:
                data = await websocket.receive_json()
            except Exception as receive_error:
                logger.error(f"Error receiving WebSocket message: {receive_error}", exc_info=True)
                break
            
            message_type = data.get("type")
            
            if message_type == "message":
                # Process user message
                user_message = data.get("content")
                file_ids = data.get("file_ids", [])
                open_files = data.get("open_files", [])
                context = session_manager.get_session(session_id)
                
                if not context:
                    context = ConversationContext(session_id)
                    session_manager.update_session(session_id, context)
                
                # Run process_message in background task to avoid blocking the message loop
                # This allows other messages (like approve_plan) to be received while processing
                async def process_message_task():
                    try:
                        await agent_wrapper.process_message(
                            user_message,
                            context,
                            session_id,
                            file_ids=file_ids if file_ids else None,
                            open_files=open_files if open_files else None
                        )
                        session_manager.update_session(session_id, context)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
                        await ws_manager.send_event(session_id, "error", {"message": str(e)})
                
                # Start background task - don't await it
                asyncio.create_task(process_message_task())
            
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
            
            elif message_type == "stop_generation":
                # Stop generation
                await agent_wrapper.stop_generation(session_id)
    
    except WebSocketDisconnect as e:
        ws_manager.disconnect(websocket, session_id)
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Exception in WebSocket endpoint for session {session_id}: {e}", exc_info=True)
        ws_manager.disconnect(websocket, session_id)


if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug
    )

