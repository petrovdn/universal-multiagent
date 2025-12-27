"""
Direct test of Gmail MCP server.
Tests MCP connection and queries directly to verify emails are accessible.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.mcp_loader import get_mcp_manager
from src.utils.config_loader import get_config


async def test_gmail_mcp():
    """Test Gmail MCP connection and queries."""
    print("=" * 80)
    print("Gmail MCP Direct Test")
    print("=" * 80)
    print()
    
    # Get MCP manager
    mcp_manager = get_mcp_manager()
    
    # Test 1: Connect to Gmail MCP
    print("1. Testing MCP connection...")
    try:
        results = await mcp_manager.connect_all()
        gmail_connected = results.get("gmail", False)
        print(f"   Gmail connection: {'✓ Connected' if gmail_connected else '✗ Failed'}")
        if not gmail_connected:
            print("   ERROR: Cannot connect to Gmail MCP server")
            return
    except Exception as e:
        print(f"   ERROR: Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Test 2: List available tools
    print("2. Listing available tools...")
    try:
        connection = mcp_manager.connections.get("gmail")
        if connection:
            tools = connection.get_tools()
            print(f"   Found {len(tools)} tools:")
            for tool_name in sorted(tools.keys()):
                tool_desc = tools[tool_name].get('description', '')[:60]
                print(f"   - {tool_name}: {tool_desc}...")
        else:
            print("   ERROR: Gmail connection not found")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print()
    
    # Test 3: Get Gmail profile
    print("3. Getting Gmail profile...")
    try:
        result = await mcp_manager.call_tool(
            "gmail_get_profile",
            {},
            server_name="gmail"
        )
        print(f"   Result: {result}")
        
        # Parse result
        if isinstance(result, str):
            try:
                profile = json.loads(result)
            except:
                profile = {"raw": result}
        else:
            profile = result
        
        if isinstance(profile, dict):
            email = profile.get('emailAddress', 'Unknown')
            messages_total = profile.get('messagesTotal', 0)
            threads_total = profile.get('threadsTotal', 0)
            print(f"   Email: {email}")
            print(f"   Total messages: {messages_total}")
            print(f"   Total threads: {threads_total}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 4: Get unread count
    print("4. Getting unread count...")
    try:
        result = await mcp_manager.call_tool(
            "gmail_get_unread_count",
            {"labelId": "INBOX"},
            server_name="gmail"
        )
        print(f"   Result: {result}")
        
        if isinstance(result, str):
            try:
                count_data = json.loads(result)
            except:
                count_data = {"raw": result}
        else:
            count_data = result
        
        if isinstance(count_data, dict):
            unread = count_data.get('unreadCount', 0)
            total = count_data.get('totalCount', 0)
            print(f"   Unread emails: {unread}")
            print(f"   Total emails in inbox: {total}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print()
    
    # Test 5: List recent messages (last 10)
    print("5. Listing recent messages (last 10)...")
    try:
        result = await mcp_manager.call_tool(
            "gmail_list_messages",
            {"maxResults": 10, "labelIds": ["INBOX"]},
            server_name="gmail"
        )
        
        # Parse result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            messages = data.get('messages', [])
            count = data.get('count', len(messages))
            print(f"   Found {count} messages")
            
            if messages:
                print("   Recent messages:")
                for i, msg in enumerate(messages[:5], 1):
                    subject = msg.get('subject', 'No subject')[:50]
                    from_addr = msg.get('from', 'Unknown')[:40]
                    date = msg.get('date', '')
                    msg_id = msg.get('id', '')
                    print(f"   {i}. {subject}")
                    print(f"      From: {from_addr}")
                    print(f"      Date: {date}")
                    print(f"      ID: {msg_id[:20]}...")
                    print()
            else:
                print("   WARNING: No messages found!")
        else:
            print(f"   Raw result: {result}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 6: Search emails newer than 7 days
    print("6. Searching emails newer than 7 days (newer_than:7d)...")
    try:
        result = await mcp_manager.call_tool(
            "gmail_search",
            {"query": "newer_than:7d", "maxResults": 20},
            server_name="gmail"
        )
        
        # Parse result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            messages = data.get('messages', [])
            count = data.get('count', len(messages))
            query = data.get('query', '')
            print(f"   Query: {query}")
            print(f"   Found {count} messages")
            
            if messages:
                print("   Emails from last 7 days:")
                for i, msg in enumerate(messages[:10], 1):
                    subject = msg.get('subject', 'No subject')[:50]
                    from_addr = msg.get('from', 'Unknown')[:40]
                    date = msg.get('date', '')
                    msg_id = msg.get('id', '')
                    print(f"   {i}. {subject}")
                    print(f"      From: {from_addr}")
                    print(f"      Date: {date}")
                    print(f"      ID: {msg_id[:20]}...")
                    print()
            else:
                print("   WARNING: No emails found for 'newer_than:7d'!")
        else:
            print(f"   Raw result: {result}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 7: Try different search queries
    print("7. Testing different search queries...")
    
    test_queries = [
        ("newer_than:1d", "Last 1 day"),
        ("newer_than:3d", "Last 3 days"),
        ("newer_than:7d", "Last 7 days"),
        ("newer_than:30d", "Last 30 days"),
        ("is:unread", "Unread emails"),
        ("in:inbox", "All inbox emails"),
    ]
    
    for query, description in test_queries:
        try:
            print(f"   Testing: {description} ({query})")
            result = await mcp_manager.call_tool(
                "gmail_search",
                {"query": query, "maxResults": 5},
                server_name="gmail"
            )
            
            if isinstance(result, str):
                try:
                    data = json.loads(result)
                except:
                    data = {"raw": result}
            else:
                data = result
            
            if isinstance(data, dict):
                count = data.get('count', 0)
                messages = data.get('messages', [])
                if not count and isinstance(messages, list):
                    count = len(messages)
                print(f"      Found: {count} emails")
            else:
                print(f"      Result: {str(result)[:100]}...")
        except Exception as e:
            print(f"      ERROR: {e}")
    
    print()
    
    # Test 8: Get first email details if any exist
    print("8. Getting details of first email (if exists)...")
    try:
        # First, get list of messages
        result = await mcp_manager.call_tool(
            "gmail_list_messages",
            {"maxResults": 1, "labelIds": ["INBOX"]},
            server_name="gmail"
        )
        
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except:
                data = {"raw": result}
        else:
            data = result
        
        if isinstance(data, dict):
            messages = data.get('messages', [])
            if messages:
                msg_id = messages[0].get('id')
                if msg_id:
                    print(f"   Getting details for message ID: {msg_id}")
                    detail_result = await mcp_manager.call_tool(
                        "gmail_get_message",
                        {"messageId": msg_id, "format": "metadata"},
                        server_name="gmail"
                    )
                    
                    if isinstance(detail_result, str):
                        try:
                            detail_data = json.loads(detail_result)
                        except:
                            detail_data = {"raw": detail_result}
                    else:
                        detail_data = detail_result
                    
                    if isinstance(detail_data, dict):
                        print(f"   Subject: {detail_data.get('subject', 'N/A')}")
                        print(f"   From: {detail_data.get('from', 'N/A')}")
                        print(f"   Date: {detail_data.get('date', 'N/A')}")
                        print(f"   Labels: {detail_data.get('labels', [])}")
            else:
                print("   No messages to get details for")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Test completed")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_gmail_mcp())

