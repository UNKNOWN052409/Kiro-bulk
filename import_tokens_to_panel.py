"""Import saved tokens from kiro_tokens.jsonl to the 9Router panel."""
import json
import os
import sys
import time
import requests

PANEL_URL = "https://ourproxy.sryze.cc"
PANEL_PASSWORD = "7894561230"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiro_tokens.jsonl')

def check_panel():
    """Check if panel is accessible."""
    try:
        resp = requests.post(f"{PANEL_URL}/api/auth/login", 
                           json={"password": PANEL_PASSWORD}, timeout=10)
        return resp.ok
    except Exception:
        return False

def import_tokens():
    """Import all saved tokens to the panel."""
    if not os.path.exists(TOKEN_FILE):
        print("[!] No token file found")
        return
    
    # Read tokens
    tokens = []
    with open(TOKEN_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                tokens.append(json.loads(line))
    
    print(f"[*] Found {len(tokens)} saved tokens")
    
    # Check panel
    if not check_panel():
        print("[!] Panel is not accessible")
        return
    
    # Login to panel
    session = requests.Session()
    resp = session.post(f"{PANEL_URL}/api/auth/login",
                       json={"password": PANEL_PASSWORD}, timeout=10)
    if not resp.ok:
        print("[!] Panel login failed")
        return
    print("[+] Panel login successful")
    
    # Import each token
    success = 0
    failed = 0
    for token_data in tokens:
        email = token_data['email']
        rt = token_data['refreshToken']
        
        try:
            resp = session.post(f"{PANEL_URL}/api/oauth/kiro/import",
                               json={
                                   "refreshToken": rt,
                                   "region": token_data.get('region', 'us-east-1'),
                                   "authMethod": token_data.get('authMethod', 'builder-id'),
                                   "startUrl": token_data.get('startUrl', 'https://view.awsapps.com/start'),
                                   "name": email
                               }, timeout=30)
            if resp.ok:
                print(f"[+] Imported: {email}")
                success += 1
            else:
                print(f"[!] Failed: {email} - {resp.status_code} {resp.text[:100]}")
                failed += 1
        except Exception as e:
            print(f"[!] Error: {email} - {e}")
            failed += 1
        
        time.sleep(0.5)  # Small delay between imports
    
    print(f"\n[*] Summary: {success} imported, {failed} failed")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        if check_panel():
            print("[+] Panel is accessible")
        else:
            print("[!] Panel is NOT accessible")
    else:
        import_tokens()
