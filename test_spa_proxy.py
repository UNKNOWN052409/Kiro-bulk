"""
Test: Can the profile.aws.amazon.com SPA load through the residential proxy?
Use very long timeouts and check what happens step by step.
"""

import requests, socks, socket, time, json, random

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = str(random.randint(100000, 999999999))

SOCKS5_HOST = 'gw.proxyrise.com'
SOCKS5_PORT = 443
SOCKS5_USER = f'res-us-sid-{PROXY_SESSION_ID}'

print(f"Session: {PROXY_SESSION_ID}")

# Create a requests session through SOCKS5
session = requests.Session()
session.proxies = {
    'http': f'socks5://{SOCKS5_USER}:{PROXYRISE_API_KEY}@{SOCKS5_HOST}:{SOCKS5_PORT}',
    'https': f'socks5://{SOCKS5_USER}:{PROXYRISE_API_KEY}@{SOCKS5_HOST}:{SOCKS5_PORT}',
}
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
})

# Test 1: GET profile.aws.amazon.com
print("\n=== Test 1: GET profile.aws.amazon.com ===")
try:
    resp = session.get('https://profile.aws.amazon.com/', timeout=60)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
    print(f"  Body length: {len(resp.text)}")
    print(f"  Body preview: {resp.text[:300]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 2: GET profile.aws.amazon.com with workflowID
print("\n=== Test 2: GET profile.aws.amazon.com/?workflowID=test ===")
try:
    resp = session.get('https://profile.aws.amazon.com/?workflowID=test123#/signup/start', timeout=60)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
    print(f"  Body length: {len(resp.text)}")
    print(f"  Body preview: {resp.text[:300]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 3: POST get-config
print("\n=== Test 3: POST /api/get-config ===")
try:
    resp = session.post('https://profile.aws.amazon.com/api/get-config', 
                        json={}, timeout=60)
    print(f"  Status: {resp.status_code}")
    print(f"  Body: {resp.text[:300]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 4: POST get-app-context (will likely fail without valid workflowID)
print("\n=== Test 4: POST /api/get-app-context ===")
try:
    resp = session.post('https://profile.aws.amazon.com/api/get-app-context',
                        json={'workflowID': 'test123'}, timeout=60)
    print(f"  Status: {resp.status_code}")
    print(f"  Body: {resp.text[:300]}")
except Exception as e:
    print(f"  Error: {e}")

print("\nDone!")
