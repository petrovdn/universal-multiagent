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
    # #region agent log
    import json as _debug_json; import time as _debug_time
    try:
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
            _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_search_start","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:39","message":"Starting Unsplash image search","data":{"query":query,"orientation":orientation,"per_page":per_page},"sessionId":"debug-session","runId":"run1","hypothesisId":"4E"}) + '\n')
    except (PermissionError, OSError):
        pass  # Ignore if debug log is not writable (e.g. in tests)
    # #endregion
    
    try:
        config = get_config()
        access_key = getattr(config, 'unsplash_access_key', None)
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_key","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:48","message":"Unsplash API key check","data":{"has_key":bool(access_key),"key_length":len(access_key) if access_key else 0},"sessionId":"debug-session","runId":"run1","hypothesisId":"4F"}) + '\n')
        except (PermissionError, OSError):
            pass
        # #endregion
        
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
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_request","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:64","message":"Sending request to Unsplash API","data":{"url":url,"query":query,"orientation":orientation},"sessionId":"debug-session","runId":"run1","hypothesisId":"4G"}) + '\n')
        except (PermissionError, OSError):
            pass
        # #endregion
        
        async with aiohttp.ClientSession() as session:
            # TEMPORARY: Disable SSL verification for macOS certificate issue
            # TODO: Fix by installing certificates: /Applications/Python\ 3.12/Install\ Certificates.command
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with session.get(url, params=params, ssl=ssl_context) as response:
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                        _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_response","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:71","message":"Received response from Unsplash API","data":{"status":response.status,"content_type":response.headers.get('content-type','')},"sessionId":"debug-session","runId":"run1","hypothesisId":"4H"}) + '\n')
                except (PermissionError, OSError):
                    pass
                # #endregion
                
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                            _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_results","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:80","message":"Parsed Unsplash API response","data":{"results_count":len(results),"total_results":data.get("total",0)},"sessionId":"debug-session","runId":"run1","hypothesisId":"4I"}) + '\n')
                    except (PermissionError, OSError):
                        pass
                    # #endregion
                    
                    if results:
                        # Return first result
                        photo = results[0]
                        urls = photo.get("urls", {})
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_photo","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:90","message":"Processing first photo from results","data":{"has_urls":bool(urls),"url_keys":list(urls.keys()) if urls else [],"raw_url":urls.get("raw","")[:80] if urls else "","regular_url":urls.get("regular","")[:80] if urls else "","small_url":urls.get("small","")[:80] if urls else ""},"sessionId":"debug-session","runId":"run1","hypothesisId":"4J"}) + '\n')
                        except (PermissionError, OSError):
                            pass
                        # #endregion
                        
                        result = {
                            "url": urls.get("raw", ""),
                            "regular_url": urls.get("regular", ""),
                            "small_url": urls.get("small", ""),
                            "description": photo.get("description") or photo.get("alt_description", ""),
                            "author": photo.get("user", {}).get("name", "Unknown"),
                            "author_url": photo.get("user", {}).get("links", {}).get("html", "")
                        }
                        
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_result","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:104","message":"Returning image data","data":{"has_url":bool(result["url"]),"has_regular_url":bool(result["regular_url"]),"has_small_url":bool(result["small_url"]),"description":result["description"][:50] if result["description"] else ""},"sessionId":"debug-session","runId":"run1","hypothesisId":"4K"}) + '\n')
                        except (PermissionError, OSError):
                            pass
                        # #endregion
                        
                        return result
                    else:
                        logger.info(f"[UnsplashClient] No images found for query: {query}")
                        # #region agent log
                        try:
                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_no_results","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:114","message":"No images found","data":{"query":query},"sessionId":"debug-session","runId":"run1","hypothesisId":"4L"}) + '\n')
                        except (PermissionError, OSError):
                            pass
                        # #endregion
                        return None
                else:
                    error_text = await response.text()
                    logger.warning(f"[UnsplashClient] Unsplash API error {response.status}: {error_text}")
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                            _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_error","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:121","message":"Unsplash API error","data":{"status":response.status,"error_text":error_text[:200]},"sessionId":"debug-session","runId":"run1","hypothesisId":"4M"}) + '\n')
                    except (PermissionError, OSError):
                        pass
                    # #endregion
                    return None
                    
    except Exception as e:
        logger.error(f"[UnsplashClient] Error searching Unsplash: {e}", exc_info=True)
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f:
                _debug_f.write(_debug_json.dumps({"id":f"log_{int(_debug_time.time()*1000)}_unsplash_exception","timestamp":int(_debug_time.time()*1000),"location":"unsplash_client.py:129","message":"Exception in Unsplash search","data":{"error":str(e),"error_type":type(e).__name__},"sessionId":"debug-session","runId":"run1","hypothesisId":"4N"}) + '\n')
        except (PermissionError, OSError):
            pass
        # #endregion
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
