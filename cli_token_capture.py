#!/usr/bin/env python3
"""
Kiro CLI Token Capture Script
==============================
Automates the full AWS Builder ID device auth flow for Kiro CLI:
1. Registers a client with AWS SSO OIDC
2. Starts device authorization to get a user code
3. Automates browser login with the email + OTP from Gmail
4. Captures the resulting access/refresh token
5. Saves the token for panel import

Usage:
  python3 cli_token_capture.py --email user@havenhaus.in
"""
import sys
import os
import time
import json
import argparse
import boto3
from botocore.exceptions import ClientError, WaiterError

# AWS Builder ID SSO OIDC endpoint
SSO_OIDC_ENDPOINT = "https://oidc.us-east-1.amazonaws.com"
START_URL = "https://view.awsapps.com/start"
CLIENT_NAME = "kirocli"
CLIENT_TYPE = "public"

def register_client():
    """Register a public client with AWS SSO OIDC."""
    client = boto3.client('sso-oidc', region_name='us-east-1')
    resp = client.register_client(
        clientName=CLIENT_NAME,
        clientType=CLIENT_TYPE
    )
    return resp

def start_device_auth(client_id, client_secret):
    """Start device authorization flow."""
    client = boto3.client('sso-oidc', region_name='us-east-1')
    resp = client.start_device_authorization(
        clientId=client_id,
        clientSecret=client_secret,
        startUrl=START_URL
    )
    return resp

def poll_for_token(client_id, client_secret, device_code, interval, max_time=300):
    """Poll CreateToken until the user completes auth in browser."""
    client = boto3.client('sso-oidc', region_name='us-east-1')
    start_time = time.time()
    poll_count = 0
    
    while time.time() - start_time < max_time:
        poll_count += 1
        try:
            resp = client.create_token(
                clientId=client_id,
                clientSecret=client_secret,
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=device_code
            )
            print(f"    [Poll #{poll_count}] Token received!")
            return resp
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ('AuthorizationPendingException', 'SlowDownException'):
                # Only print every 30 polls to avoid spam
                if poll_count % 30 == 0:
                    print(f"    [Poll #{poll_count}] Still waiting... ({int(time.time()-start_time)}s)")
                time.sleep(interval)
                continue
            elif error_code == 'ExpiredTokenException':
                print(f"    [Poll #{poll_count}] ERROR: Device code expired.")
                break
            elif error_code == 'InvalidClientException':
                print(f"    [Poll #{poll_count}] ERROR: Invalid client.")
                break
            elif error_code == 'InvalidGrantException':
                print(f"    [Poll #{poll_count}] ERROR: Invalid grant - auth might have been denied or code already used.")
                break
            elif error_code == 'UnauthorizedClientException':
                print(f"    [Poll #{poll_count}] ERROR: Unauthorized client.")
                break
            else:
                print(f"    [Poll #{poll_count}] ERROR: {error_code}: {e.response['Error'].get('Message', '')}")
                break
        except Exception as e:
            print(f"    [Poll #{poll_count}] Unexpected error: {e}")
            break
        time.sleep(interval)
    
    print(f"    [Poll #{poll_count}] Timeout after {int(time.time()-start_time)}s")
    return None

def main():
    parser = argparse.ArgumentParser(description='Capture Kiro CLI token via device auth')
    parser.add_argument('--email', required=True, help='Email address for the AWS account')
    parser.add_argument('--output', default=None, help='Output file for the token JSON')
    args = parser.parse_args()
    
    print(f"[*] Starting token capture for: {args.email}")
    
    # Step 1: Register client
    print("[*] Step 1: Registering OIDC client...")
    reg = register_client()
    client_id = reg['clientId']
    client_secret = reg['clientSecret']
    print(f"    Client ID: {client_id}")
    
    # Step 2: Start device auth
    print("[*] Step 2: Starting device authorization...")
    device = start_device_auth(client_id, client_secret)
    user_code = device['userCode']
    verification_uri = device['verificationUriComplete']
    device_code = device['deviceCode']
    interval = device['interval']
    expires_in = device['expiresIn']
    
    print(f"    User Code: {user_code}")
    print(f"    Verification URI: {verification_uri}")
    print(f"    Device Code: {device_code}")
    print(f"    Expires in: {expires_in}s, Poll interval: {interval}s")
    
    # Save the device auth info for the browser automation to use
    device_auth_info = {
        'client_id': client_id,
        'client_secret': client_secret,
        'device_code': device_code,
        'user_code': user_code,
        'verification_uri': verification_uri,
        'start_url': START_URL,
        'email': args.email,
        'interval': interval,
        'expires_in': expires_in,
        'timestamp': time.time()
    }
    
    # Save to a temp file that the browser automation can read
    auth_file = '/tmp/kiro_device_auth.json'
    with open(auth_file, 'w') as f:
        json.dump(device_auth_info, f, indent=2)
    print(f"    Saved device auth info to: {auth_file}")
    
    # Step 3: Wait for browser automation to complete (it reads the auth file and does the login)
    # Then poll for the token
    print("[*] Step 3: Waiting for browser authentication...")
    print("    The browser automation will handle the login.")
    print("    Polling for token...")
    
    token_resp = poll_for_token(client_id, client_secret, device_code, interval, max_time=expires_in)
    
    if token_resp:
        print("[+] Token captured successfully!")
        token_data = {
            'email': args.email,
            'access_token': token_resp.get('accessToken', ''),
            'refresh_token': token_resp.get('refreshToken', ''),
            'token_type': token_resp.get('tokenType', 'Bearer'),
            'expires_in': token_resp.get('expiresIn', 0),
            'expires_at': time.time() + token_resp.get('expiresIn', 0),
            'id_token': token_resp.get('idToken', ''),
            'client_id': client_id,
            'client_secret': client_secret,
            'start_url': START_URL,
            'region': 'us-east-1',
            'captured_at': time.time()
        }
        
        # Save token
        output_file = args.output or f"/tmp/kiro_token_{args.email.replace('@', '_').replace('.', '_')}.json"
        with open(output_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"    Token saved to: {output_file}")
        return 0
    else:
        print("[-] Failed to capture token (timeout or error)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
