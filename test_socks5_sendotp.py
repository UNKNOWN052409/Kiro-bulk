#!/usr/bin/env python3
"""
Test the full flow through profile.aws.amazon.com API using SOCKS5 US proxy.
This simulates what the SPA does: get-config, get-app-context, start, then send-otp.
"""

import requests, json, uuid, random, string, time

API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY = f'socks5://res-US:{API_KEY}@gw.proxyrise.com:443'

# Generate a test email (use a new one)
prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
email = f"{prefix}@havenhaus.in"
print(f"Test email: {email}")

# Test IPs first
try:
    resp = requests.get('https://api.ipquery.io/?format=json', proxies={'https': PROXY}, timeout=15)
    ip_data = resp.json()
    print(f"Proxy IP: {ip_data.get('ip')} ({ip_data.get('city')}, {ip_data.get('country_code')})")
except Exception as e:
    print(f"Proxy check failed: {e}")

headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Referer': 'https://profile.aws.amazon.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Step 1: get-config
print("\n[1] GET-CONFIG:")
resp = requests.post('https://profile.aws.amazon.com/api/get-config', json={}, 
                    headers=headers, proxies={'https': PROXY}, timeout=30)
print(f"  HTTP {resp.status_code}: {resp.text[:200]}")

# Step 2: get-app-context (needs a fake workflowID - this will fail but let's see)
print("\n[2] GET-APP-CONTEXT (fake workflowID):")
fake_wid = str(uuid.uuid4())
resp = requests.post('https://profile.aws.amazon.com/api/get-app-context', 
                    json={"workflowID": fake_wid}, headers=headers, 
                    proxies={'https': PROXY}, timeout=30)
print(f"  HTTP {resp.status_code}: {resp.text[:200]}")

# Step 3: start (needs real workflowID)
print("\n[3] START (fake workflowID):")
resp = requests.post('https://profile.aws.amazon.com/api/start', 
                    json={"workflowID": fake_wid, "browserData": {"attributes": {"fingerprint": "ECdITeCs:test", "eventTimestamp": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + '.000Z', "timeSpentOnPage": "100", "eventType": "PageLoad", "ubid": "118-123456-7890123"}, "cookies": {}}},
                    headers=headers, proxies={'https': PROXY}, timeout=30)
print(f"  HTTP {resp.status_code}: {resp.text[:300]}")

# Step 4: send-otp (the critical one that was returning BLOCKED)
print("\n[4] SEND-OTP (simulated):")
fake_ws = str(uuid.uuid4())
fingerprint = "ECdITeCs:" + ''.join(random.choices(string.ascii_letters + string.digits + '+/=', k=5700))
resp = requests.post('https://profile.aws.amazon.com/api/send-otp',
                    json={
                        "workflowState": fake_ws,
                        "email": email,
                        "browserData": {
                            "attributes": {
                                "fingerprint": fingerprint,
                                "eventTimestamp": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + '.000Z',
                                "timeSpentOnPage": "5000",
                                "pageName": "EMAIL_COLLECTION",
                                "eventType": "PageSubmit",
                                "ubid": "118-123456-7890123"
                            },
                            "cookies": {}
                        }
                    },
                    headers=headers, proxies={'https': PROXY}, timeout=60)
print(f"  HTTP {resp.status_code}: {resp.text[:300]}")

if 'BLOCKED' in resp.text:
    print("\n  ✗ Still BLOCKED - but this is expected with a fake workflowState")
    print("  Need to test with REAL workflowState from actual browser flow")
elif 'VALID' in resp.text or 'invalid' in resp.text.lower():
    print("\n  ✓ NOT blocked by TES! The 400 is about invalid workflowState, not IP")
else:
    print(f"\n  Response: {resp.text[:200]}")

print("\n" + "="*60)
