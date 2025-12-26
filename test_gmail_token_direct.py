"""
Direct test of Gmail token - check if it's valid and can be used.
"""

import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def test_gmail_token():
    """Test Gmail token directly."""
    token_path = Path("config/gmail_token.json")
    
    print("=" * 80)
    print("Gmail Token Direct Test")
    print("=" * 80)
    print()
    
    # Read token file
    print("1. Reading token file...")
    if not token_path.exists():
        print(f"   ERROR: Token file not found at {token_path}")
        return
    
    with open(token_path, 'r') as f:
        token_data = json.load(f)
    
    print(f"   Token file exists: {token_path}")
    print(f"   Has refresh_token: {token_data.get('refresh_token') is not None}")
    print(f"   Has token: {token_data.get('token') is not None}")
    print(f"   Has client_id: {token_data.get('client_id') is not None}")
    print(f"   Has client_secret: {token_data.get('client_secret') is not None}")
    print(f"   Scopes: {token_data.get('scopes', [])}")
    print()
    
    # Load credentials
    print("2. Loading credentials...")
    try:
        creds = Credentials.from_authorized_user_file(
            str(token_path),
            token_data.get('scopes', [])
        )
        print(f"   Credentials loaded successfully")
        print(f"   Valid: {creds.valid}")
        print(f"   Expired: {creds.expired}")
        print(f"   Has refresh_token: {creds.refresh_token is not None}")
    except Exception as e:
        print(f"   ERROR: Failed to load credentials: {e}")
        return
    
    print()
    
    # Try to refresh if expired
    print("3. Checking token expiry...")
    if creds.expired:
        print("   Token is expired")
        if creds.refresh_token:
            print("   Attempting to refresh token...")
            try:
                creds.refresh(Request())
                print("   ✓ Token refreshed successfully")
                print(f"   Valid: {creds.valid}")
                
                # Save refreshed token
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
                print("   ✓ Refreshed token saved")
            except Exception as e:
                print(f"   ✗ Failed to refresh token: {e}")
                return
        else:
            print("   ✗ No refresh_token available - cannot refresh")
            print("   You need to re-authenticate to get a new token with refresh_token")
            return
    else:
        print("   Token is still valid (not expired)")
    
    print()
    
    # Test Gmail API call
    print("4. Testing Gmail API call...")
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Get profile
        print("   Getting Gmail profile...")
        profile = service.users().getProfile(userId='me').execute()
        print(f"   ✓ Profile retrieved")
        print(f"   Email: {profile.get('emailAddress')}")
        print(f"   Messages total: {profile.get('messagesTotal')}")
        print(f"   Threads total: {profile.get('threadsTotal')}")
        
        print()
        
        # List messages
        print("5. Listing recent messages...")
        results = service.users().messages().list(
            userId='me',
            maxResults=10,
            labelIds=['INBOX']
        ).execute()
        
        messages = results.get('messages', [])
        print(f"   Found {len(messages)} messages")
        
        if messages:
            print("   Recent messages:")
            for i, msg in enumerate(messages[:5], 1):
                msg_detail = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                
                headers = msg_detail.get('payload', {}).get('headers', [])
                from_addr = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                print(f"   {i}. {subject[:50]}")
                print(f"      From: {from_addr[:40]}")
                print(f"      Date: {date}")
        
        print()
        
        # Search messages newer than 7 days
        print("6. Searching messages newer than 7 days...")
        search_results = service.users().messages().list(
            userId='me',
            q='newer_than:7d',
            maxResults=20
        ).execute()
        
        search_messages = search_results.get('messages', [])
        print(f"   Found {len(search_messages)} messages newer than 7 days")
        
        if search_messages:
            print("   Emails from last 7 days:")
            for i, msg in enumerate(search_messages[:5], 1):
                msg_detail = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                
                headers = msg_detail.get('payload', {}).get('headers', [])
                from_addr = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                print(f"   {i}. {subject[:50]}")
                print(f"      From: {from_addr[:40]}")
                print(f"      Date: {date}")
        else:
            print("   ⚠ No messages found for 'newer_than:7d'")
        
    except HttpError as e:
        print(f"   ERROR: Gmail API error: {e}")
        print(f"   Status: {e.resp.status}")
        print(f"   Content: {e.content.decode() if e.content else 'None'}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Test completed")
    print("=" * 80)


if __name__ == "__main__":
    test_gmail_token()

