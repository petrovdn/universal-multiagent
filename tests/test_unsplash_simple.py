"""
Simple standalone test for Unsplash API (without debug logging).
Run: python3 tests/test_unsplash_simple.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from src.utils.config_loader import get_config


async def test_unsplash_direct():
    """Test Unsplash API directly without debug logging."""
    print("🔍 Testing Unsplash API integration...\n")
    
    # Get API key
    config = get_config()
    access_key = getattr(config, 'unsplash_access_key', None)
    
    print(f"1. API Key check:")
    print(f"   - Has key: {bool(access_key)}")
    print(f"   - Key length: {len(access_key) if access_key else 0}")
    
    if not access_key:
        print("   ❌ UNSPLASH_ACCESS_KEY not configured!")
        return False
    
    print(f"   ✅ API key configured\n")
    
    # Test queries
    queries = [
        "ancient egypt pyramids",
        "egypt pharaoh",
        "ancient egypt art"
    ]
    
    print(f"2. Testing {len(queries)} search queries:\n")
    
    for i, query in enumerate(queries, 1):
        print(f"   Query {i}: '{query}'")
        
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "orientation": "landscape",
            "per_page": 1,
            "client_id": access_key
        }
        
        try:
            # Disable SSL verification for macOS certificate issue
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, ssl=ssl_context) as response:
                    print(f"      - Status: {response.status}")
                    print(f"      - Content-Type: {response.headers.get('content-type', 'N/A')}")
                    
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        total = data.get("total", 0)
                        
                        print(f"      - Total results: {total}")
                        print(f"      - Returned results: {len(results)}")
                        
                        if results:
                            photo = results[0]
                            urls = photo.get("urls", {})
                            
                            raw_url = urls.get("raw", "")
                            regular_url = urls.get("regular", "")
                            small_url = urls.get("small", "")
                            
                            print(f"      - URL formats available:")
                            print(f"        * raw: {'✅' if raw_url else '❌'} ({len(raw_url)} chars)")
                            print(f"        * regular: {'✅' if regular_url else '❌'} ({len(regular_url)} chars)")
                            print(f"        * small: {'✅' if small_url else '❌'} ({len(small_url)} chars)")
                            
                            if regular_url:
                                print(f"      - Sample URL: {regular_url[:80]}...")
                                print(f"      ✅ SUCCESS\n")
                            else:
                                print(f"      ❌ NO URLS RETURNED!\n")
                                print(f"         Full photo data: {photo}\n")
                        else:
                            print(f"      ⚠️  No images found for this query\n")
                    else:
                        error_text = await response.text()
                        print(f"      ❌ API Error: {response.status}")
                        print(f"      {error_text[:200]}\n")
        
        except Exception as e:
            print(f"      ❌ Exception: {e}\n")
    
    print("\n✅ Unsplash API test completed!")
    return True


if __name__ == "__main__":
    asyncio.run(test_unsplash_direct())
