"""
Unsplash API client for searching and retrieving images.
Used for adding relevant images to presentation slides.
"""

import aiohttp
import logging
from typing import Optional, Dict, Any
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


async def search_unsplash_image(
    query: str,
    orientation: str = "landscape",
    per_page: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Search for an image on Unsplash using a query string.
    
    Args:
        query: Search query (e.g., "ancient rome architecture")
        orientation: Image orientation ("landscape", "portrait", "squarish")
        per_page: Number of results to return (default: 1, returns first result)
    
    Returns:
        Dict with image data:
        {
            "url": "https://images.unsplash.com/...",
            "regular_url": "https://images.unsplash.com/...",
            "small_url": "https://images.unsplash.com/...",
            "description": "Image description",
            "author": "Photographer name",
            "author_url": "https://unsplash.com/@..."
        }
        or None if no image found or error occurred
    """
    try:
        config = get_config()
        access_key = getattr(config, 'unsplash_access_key', None)
        
        if not access_key:
            logger.warning("[UnsplashClient] UNSPLASH_ACCESS_KEY not configured, skipping image search")
            return None
        
        # Unsplash API endpoint
        url = "https://api.unsplash.com/search/photos"
        
        params = {
            "query": query,
            "orientation": orientation,
            "per_page": per_page,
            "client_id": access_key
        }
        
        async with aiohttp.ClientSession() as session:
            # TEMPORARY: Disable SSL verification for macOS certificate issue
            # TODO: Fix by installing certificates: /Applications/Python\ 3.12/Install\ Certificates.command
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with session.get(url, params=params, ssl=ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    
                    if results:
                        # Return first result
                        photo = results[0]
                        urls = photo.get("urls", {})
                        
                        result = {
                            "url": urls.get("raw", ""),
                            "regular_url": urls.get("regular", ""),
                            "small_url": urls.get("small", ""),
                            "description": photo.get("description") or photo.get("alt_description", ""),
                            "author": photo.get("user", {}).get("name", "Unknown"),
                            "author_url": photo.get("user", {}).get("links", {}).get("html", "")
                        }
                        
                        return result
                    else:
                        logger.info(f"[UnsplashClient] No images found for query: {query}")
                        return None
                else:
                    error_text = await response.text()
                    logger.warning(f"[UnsplashClient] Unsplash API error {response.status}: {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"[UnsplashClient] Error searching Unsplash: {e}", exc_info=True)
        return None


async def get_unsplash_image_url(query: str, orientation: str = "landscape") -> Optional[str]:
    """
    Simplified function to get just the image URL.
    
    Args:
        query: Search query
        orientation: Image orientation
    
    Returns:
        Image URL (regular size) or None
    """
    image_data = await search_unsplash_image(query, orientation)
    if image_data:
        # Try multiple URL formats (regular > raw > small)
        url = (
            image_data.get("regular_url") or 
            image_data.get("url") or 
            image_data.get("small_url") or
            ""
        )
        if url:
            logger.info(f"[UnsplashClient] Found image URL for '{query}': {url[:80]}...")
            return url
        else:
            logger.warning(f"[UnsplashClient] Image data returned but all URLs are empty for query: {query}")
    return None
