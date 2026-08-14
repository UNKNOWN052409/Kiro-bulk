"""
Test token capture via boto3 OIDC device flow.
Register client, start device auth, then we'll handle the browser separately.
"""
import boto3
from botocore.exceptions import ClientError
import time

SSO_OIDC_ENDPOINT = "https://oidc.us-east-1.amazonaws.com"
START_URL = "https://view.awsapps.com/start"

def main():
    print("[*] Registering OIDC client...")
    client = boto3.client('sso-oidc', region_name='us-east-1')
    
    try:
        reg = client.register_client(
            clientName='kirocli-test',
            clientType='public'
        )
        client_id = reg['clientId']
        client_secret = reg['clientSecret']
        print(f"  [+] Client ID: {client_id}")
        print(f"  [+] Client Secret: {client_secret}")
    except ClientError as e:
        print(f"  [!] Register failed: {e}")
        # Try with a unique name
        import uuid
        reg = client.register_client(
            clientName=f'kirocli-{uuid.uuid4().hex[:8]}',
            clientType='public'
        )
        client_id = reg['clientId']
        client_secret = reg['clientSecret']
        print(f"  [+] Client ID (retry): {client_id}")
    
    print("[*] Starting device authorization...")
    device = client.start_device_authorization(
        clientId=client_id,
        clientSecret=client_secret,
        startUrl=START_URL
    )
    
    user_code = device['userCode']
    verification_uri = device['verificationUriComplete']
    device_code = device['deviceCode']
    interval = device['interval']
    expires_in = device['expiresIn']
    
    print(f"  [+] User Code: {user_code}")
    print(f"  [+] Verification URI: {verification_uri}")
    print(f"  [+] Device Code: {device_code}")
    print(f"  [+] Interval: {interval}s, Expires: {expires_in}s")
    
    # Save for browser automation
    import json
    with open('/tmp/device_auth_info.json', 'w') as f:
        json.dump({
            'client_id': client_id,
            'client_secret': client_secret,
            'device_code': device_code,
            'user_code': user_code,
            'verification_uri': verification_uri,
            'start_url': START_URL,
            'email': 'ax3p0kzyk6@havenhaus.in',
            'interval': interval,
            'expires_in': expires_in,
        }, f, indent=2)
    
    print("[*] Polling for token (you have 5 minutes to complete browser auth)...")
    print(f"[*] Navigate to: {verification_uri}")
    
    start_time = time.time()
    poll_count = 0
    while time.time() - start_time < min(expires_in, 300):
        poll_count += 1
        try:
            token = client.create_token(
                clientId=client_id,
                clientSecret=client_secret,
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=device_code
            )
            print(f"\n[+] TOKEN RECEIVED after {poll_count} polls!")
            print(f"    Access Token: {token.get('accessToken', '')[:50]}...")
            print(f"    Refresh Token: {token.get('refreshToken', '')[:50]}...")
            print(f"    Expires In: {token.get('expiresIn')}s")
            
            # Save token
            with open('/tmp/captured_token.json', 'w') as f:
                json.dump({
                    'email': 'ax3p0kzyk6@havenhaus.in',
                    'access_token': token.get('accessToken', ''),
                    'refresh_token': token.get('refreshToken', ''),
                    'token_type': token.get('tokenType', 'Bearer'),
                    'expires_in': token.get('expiresIn', 0),
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'start_url': START_URL,
                    'region': 'us-east-1',
                    'captured_at': time.time(),
                }, f, indent=2)
            print(f"    Saved to /tmp/captured_token.json")
            return 0
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ('AuthorizationPendingException', 'SlowDownException'):
                if poll_count % 10 == 0:
                    print(f"    [Poll #{poll_count}] Still waiting... ({int(time.time()-start_time)}s)")
                time.sleep(interval)
                continue
            elif error_code == 'ExpiredTokenException':
                print(f"    [!] Device code expired after {poll_count} polls")
                break
            else:
                print(f"    [!] Error: {error_code}: {e.response['Error'].get('Message', '')}")
                break
        except Exception as e:
            print(f"    [!] Unexpected: {e}")
            break
        time.sleep(interval)
    
    print("[!] Failed to capture token")
    return 1

if __name__ == '__main__':
    exit(main())
