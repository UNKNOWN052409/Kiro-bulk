"""Direct API approach: use accept_user_code API then create_token immediately."""
import sys, os, time, string, random, uuid
import boto3
import requests
import json

# Step 1: Register and get device code
client = boto3.client('sso-oidc', region_name='us-east-1')
reg = client.register_client(clientName=f'kiro-{uuid.uuid4().hex[:8]}', clientType='public')
device = client.start_device_authorization(
    clientId=reg['clientId'],
    clientSecret=reg['clientSecret'],
    startUrl='https://view.awsapps.com/start'
)
user_code = device['userCode']
device_code = device['deviceCode']
expires_in = device.get('expiresIn', 600)
print(f"[+] User code: {user_code}")
print(f"[+] Device code: {device_code[:20]}...")
print(f"[+] Client ID: {reg['clientId']}")
print(f"[+] Client Secret: {reg['clientSecret'][:20]}...")

# Step 2: We need the user to authorize via browser (can't skip this)
# But after authorization, we call create_token IMMEDIATELY
# The trick: we know the authorization happens when the SPA calls accept_user_code
# Let's poll create_token very aggressively

print("\n[*] Waiting for authorization...")
print(f"[*] Open this URL in browser: https://view.awsapps.com/start/#/device?user_code={user_code}")

# Aggressive poll
start = time.time()
while time.time() - start < expires_in:
    time.sleep(0.05)  # 50ms
    try:
        resp = client.create_token(
            clientId=reg['clientId'],
            clientSecret=reg['clientSecret'],
            grantType='urn:ietf:params:oauth:grant-type:device_code',
            deviceCode=device_code
        )
        token = resp.get('refreshToken')
        if token:
            print(f"\n[+] *** TOKEN CAPTURED! ***")
            print(f"[+] Access Token: {resp.get('accessToken', '')[:50]}...")
            print(f"[+] Refresh Token: {token[:50]}...")
            print(f"[+] Expires In: {resp.get('expiresIn')}")
            with open('/tmp/kiro_token_direct.txt', 'w') as f:
                json.dump({
                    'accessToken': resp.get('accessToken'),
                    'refreshToken': token,
                    'expiresIn': resp.get('expiresIn'),
                    'clientId': reg['clientId'],
                    'clientSecret': reg['clientSecret'],
                    'region': 'us-east-1',
                    'startUrl': 'https://view.awsapps.com/start'
                }, f)
            print("[+] Token saved to /tmp/kiro_token_direct.txt")
            break
    except Exception as e:
        err_code = getattr(e, 'response', {}).get('Error', {}).get('Code', str(e))
        if err_code not in ('AuthorizationPendingException', 'SlowDownException'):
            print(f"[!] Error: {err_code}")
            break
else:
    print("[!] Timeout - token not captured")
