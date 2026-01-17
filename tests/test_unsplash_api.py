"""
Test Unsplash API integration for image search.
Tests that the Unsplash client can successfully retrieve image URLs.
"""

import asyncio
import pytest
from src.utils.unsplash_client import search_unsplash_image, get_unsplash_image_url


@pytest.mark.asyncio
async def test_unsplash_search_basic():
    """Test basic image search returns valid results."""
    result = await search_unsplash_image("ancient egypt pyramids", orientation="landscape")
    
    assert result is not None, "Unsplash search should return results"
    assert "url" in result or "regular_url" in result or "small_url" in result, "Result should have at least one URL"
    
    # At least one URL should be non-empty
    has_url = bool(result.get("url") or result.get("regular_url") or result.get("small_url"))
    assert has_url, f"At least one URL should be non-empty. Got: {result}"
    
    print(f"✅ Search results:")
    print(f"  - Raw URL: {result.get('url', '')[:80]}...")
    print(f"  - Regular URL: {result.get('regular_url', '')[:80]}...")
    print(f"  - Small URL: {result.get('small_url', '')[:80]}...")
    print(f"  - Description: {result.get('description', 'N/A')[:80]}")
    print(f"  - Author: {result.get('author', 'Unknown')}")


@pytest.mark.asyncio
async def test_unsplash_get_url():
    """Test simplified URL getter function."""
    url = await get_unsplash_image_url("ancient rome architecture")
    
    assert url is not None, "Should return an image URL"
    assert url.startswith("https://"), f"URL should start with https://, got: {url}"
    assert "unsplash.com" in url, f"URL should be from unsplash.com, got: {url}"
    
    print(f"✅ Image URL: {url[:100]}...")


@pytest.mark.asyncio
async def test_unsplash_multiple_queries():
    """Test multiple different search queries."""
    queries = [
        "ancient egypt pyramids",
        "rome colosseum",
        "greek parthenon",
        "medieval castle"
    ]
    
    results = []
    for query in queries:
        url = await get_unsplash_image_url(query)
        results.append((query, url))
        print(f"✅ Query '{query}': {url[:80] if url else 'NO URL'}...")
    
    # At least 75% of queries should return results
    successful = sum(1 for _, url in results if url is not None)
    success_rate = successful / len(queries)
    
    assert success_rate >= 0.75, f"Success rate {success_rate:.0%} below 75%. Check API rate limits."


@pytest.mark.asyncio
async def test_unsplash_no_results():
    """Test behavior when no images are found."""
    # Use a very specific/unlikely query
    result = await search_unsplash_image("xyzabc123nonexistent456query789")
    
    # Should return None gracefully
    assert result is None or result.get("url") == "", "Should handle no results gracefully"
    print("✅ No results handled gracefully")


@pytest.mark.asyncio
async def test_unsplash_all_url_formats():
    """Test that we can get different URL formats."""
    result = await search_unsplash_image("mountains landscape")
    
    if result:
        print(f"✅ All URL formats:")
        print(f"  - Raw: {bool(result.get('url'))}")
        print(f"  - Regular: {bool(result.get('regular_url'))}")
        print(f"  - Small: {bool(result.get('small_url'))}")
        
        # At least one should be present
        assert any([
            result.get("url"),
            result.get("regular_url"),
            result.get("small_url")
        ]), "At least one URL format should be available"
    else:
        pytest.skip("No results returned, cannot test URL formats")


if __name__ == "__main__":
    print("🔍 Running Unsplash API tests...\n")
    
    # Run tests
    asyncio.run(test_unsplash_search_basic())
    print()
    asyncio.run(test_unsplash_get_url())
    print()
    asyncio.run(test_unsplash_multiple_queries())
    print()
    asyncio.run(test_unsplash_no_results())
    print()
    asyncio.run(test_unsplash_all_url_formats())
    
    print("\n✅ All Unsplash tests passed!")
