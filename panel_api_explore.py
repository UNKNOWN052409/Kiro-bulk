"""
Explore the 9Router panel API to find alternative ways to add accounts.
"""
import requests
import json

PANEL_URL = "https://ourproxy.sryze.cc"
PANEL_PASSWORD = "7894561230"

def main():
    session = requests.Session()
    
    # Login
    resp = session.post(f"{PANEL_URL}/api/auth/login", 
                       json={"password": PANEL_PASSWORD}, timeout=10)
    print(f"[*] Login: {resp.status_code} {resp.text[:200]}")
    
    if not resp.ok:
        return
    
    # List providers
    resp = session.get(f"{PANEL_URL}/api/providers", timeout=10)
    print(f"[*] Providers: {resp.status_code}")
    if resp.ok:
        print(json.dumps(resp.json(), indent=2)[:500])
    
    # Check existing Kiro connections
    resp = session.get(f"{PANEL_URL}/api/oauth/kiro", timeout=10)
    print(f"\n[*] Kiro connections: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        if isinstance(data, list):
            print(f"  Count: {len(data)}")
            if data:
                print(json.dumps(data[0], indent=2)[:500])
        else:
            print(json.dumps(data, indent=2)[:500])
    
    # Try to see what the import endpoint expects
    resp = session.post(f"{PANEL_URL}/api/oauth/kiro/import",
                       json={}, timeout=10)
    print(f"\n[*] Import (empty): {resp.status_code} {resp.text[:200]}")
    
    # Try with a fake token to see the error format
    resp = session.post(f"{PANEL_URL}/api/oauth/kiro/import",
                       json={
                           "refreshToken": "fake_token_123",
                           "region": "us-east-1",
                           "authMethod": "builder-id",
                           "startUrl": "https://view.awsapps.com/start",
                           "name": "test@test.com"
                       }, timeout=10)
    print(f"\n[*] Import (fake token): {resp.status_code} {resp.text[:300]}")

if __name__ == '__main__':
    main()
