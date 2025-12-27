"""
Main entry point for the Google Workspace Multi-Agent System.
Initializes all components and starts the FastAPI server.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.config_loader import get_config, reload_config
from src.utils.logging_config import setup_logging, get_logger
from src.utils.mcp_loader import get_mcp_manager
from src.api.server import app
import uvicorn


async def initialize_system():
    """Initialize all system components."""
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        config = get_config()
        logger.info("Configuration loaded successfully")
        
        # Setup logging
        setup_logging(config.log_level)
        logger.info(f"Logging configured at {config.log_level} level")
        
        # Connect to MCP servers
        logger.info("Connecting to MCP servers...")
        mcp_manager = get_mcp_manager()
        
        # Add timeout for connections (30 seconds per server)
        import asyncio
        try:
            results = await asyncio.wait_for(mcp_manager.connect_all(), timeout=90.0)
        except asyncio.TimeoutError:
            logger.error("Timeout connecting to MCP servers")
            results = {}
            for name in mcp_manager.connections.keys():
                results[name] = mcp_manager.connections[name].connected
        
        for server, connected in results.items():
            if connected:
                logger.info(f"✅ Connected to {server} MCP server")
            else:
                logger.warning(f"⚠️  Failed to connect to {server} MCP server")
        
        logger.info("System initialization complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        raise


def main():
    """Main entry point."""
    # Initialize system
    asyncio.run(initialize_system())
    
    # Get configuration
    config = get_config()
    
    # Start FastAPI server
    logger = get_logger(__name__)
    logger.info(f"Starting server on {config.api_host}:{config.api_port}")
    
    uvicorn.run(
        "src.api.server:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )


if __name__ == "__main__":
    main()
