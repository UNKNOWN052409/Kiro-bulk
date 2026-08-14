"""Test token capture synchronously."""
import sys, os, time, uuid, boto3
from botocore.exceptions import ClientError

email = sys.argv[1] if len(sys.argv) > 1 else "testpy027@havenhaus.in"

client = boto3.client('sso-oidc', region_name='us-east-1')
reg = client.register_client(clientName=f'kiro-{uuid.uuid4().hex[:8]}', clientType='public')
device = client.start_device_authorization(
    clientId=reg['clientId'],
    clientSecret=reg['clientSecret'],
    startUrl='https://view.awsapps.com/start'
)
user_code = device['userCode']
device_code = device['deviceCode']
interval = device['interval']
expires_in = device['expiresIn']
print(f"[*] User Code: {user_code}")
print(f"[*] Interval: {interval}s, Expires: {expires_in}s")

# Poll for token
deadline = time.time() + expires_in
print(f"[*] Polling for token (deadline: {time.ctime(deadline)})...")

while time.time() < deadline:
    time.sleep(interval)
    try:
        resp = client.create_token(
            clientId=reg['clientId'],
            clientSecret=reg['clientSecret'],
            grantType='urn:ietf:params:oauth:grant-type:device_code',
            deviceCode=device_code
        )
        token = resp.get('refreshToken')
        if token:
            print(f"[+] TOKEN RECEIVED! len={len(token)}")
            print(f"    Token: {token[:50]}...")
            sys.exit(0)
    except ClientError as e:
        err = e.response['Error']['Code']
        if err in ('AuthorizationPendingException', 'SlowDownException'):
            elapsed = int(time.time() - (deadline - expires_in))
            print(f"    Waiting... ({elapsed}s elapsed)")
            continue
        else:
            print(f"[!] Unexpected error: {err}")
            break
    except Exception as e:
        print(f"[!] Error: {e}")
        break

print("[!] Token not received (timeout)")
