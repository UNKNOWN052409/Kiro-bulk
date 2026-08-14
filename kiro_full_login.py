#!/usr/bin/env python3
"""
Kiro CLI Token Capture - Full Combined Flow
=============================================
This script combines the device auth API flow and browser automation into one.
It:
1. Registers an OIDC client
2. Starts device authorization
3. Automates the browser login (password + OTP)
4. Clicks "Confirm and continue" on the authorization page
5. Polls CreateToken until the token is received
6. Saves the token to a JSON file

Usage:
  python3 kiro_full_login.py --email user@havenhaus.in --output token.json
"""
import sys
import os
import time
import json
import argparse
import csv
import imaplib
import email
import re
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

# Gmail configuration
GMAIL = "anshika31618@gmail.com"
GMAIL_PASS = "hlcveobitfwhterw"

# AWS SSO OIDC config
START_URL = "https://view.awsapps.com/start"
CLIENT_NAME = "kirocli"
CLIENT_TYPE = "public"


def get_otp_from_gmail(timeout=120, after_timestamp=None):
    """Extract OTP from Gmail Spam or Inbox folder."""
    start_time = time.time()
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL, GMAIL_PASS)
        
        while time.time() - start_time < timeout:
            for folder in ['[Gmail]/Spam', 'INBOX']:
                mail.select(f'"{folder}"')
                status, messages = mail.search(None, 'ALL')
                
                if status == 'OK' and messages[0]:
                    msg_ids = messages[0].split()
                    for msg_id in reversed(msg_ids[-20:]):
                        status2, date_data = mail.fetch(msg_id, '(INTERNALDATE)')
                        if status2 != 'OK':
                            continue
                        
                        date_str = date_data[0].decode('utf-8', errors='ignore')
                        date_match = re.search(r'"(\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2})', date_str)
                        if date_match:
                            email_dt = datetime.strptime(date_match.group(1), '%d-%b-%Y %H:%M:%S')
                            if after_timestamp and email_dt.timestamp() < after_timestamp:
                                continue
                            if time.time() - email_dt.timestamp() > 300:
                                continue
                        
                        status3, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status3 != 'OK':
                            continue
                        
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        from_addr = msg.get('From', '')
                        
                        if 'login.awsapps.com' in from_addr or 'amazonaws.com' in from_addr:
                            html_body = ''
                            text_body = ''
                            if msg.is_multipart():
                                for part in msg.walk():
                                    ct = part.get_content_type()
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        decoded = payload.decode('utf-8', errors='ignore')
                                        if ct == 'text/html':
                                            html_body = decoded
                                        elif ct == 'text/plain':
                                            text_body = decoded
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    decoded = payload.decode('utf-8', errors='ignore')
                                    if msg.get_content_type() == 'text/html':
                                        html_body = decoded
                                    else:
                                        text_body = decoded
                            
                            code_match = re.search(r'class="code"[^>]*>(\d{6})<', html_body)
                            if code_match and code_match.group(1) != '555555':
                                mail.logout()
                                return code_match.group(1)
                            
                            code_match = re.search(r'verification code[^>]*>(\d{6})', html_body, re.IGNORECASE)
                            if code_match and code_match.group(1) != '555555':
                                mail.logout()
                                return code_match.group(1)
                            
                            otp_match = re.search(r'\b(\d{6})\b', text_body)
                            if otp_match and otp_match.group(1) != '555555':
                                mail.logout()
                                return otp_match.group(1)
            
            time.sleep(3)
        
        mail.logout()
    except Exception as e:
        print(f"  Gmail error: {e}")
    
    return None


def get_account_password(email_addr, csv_file=None):
    """Get the password for an account from the CSV file."""
    if csv_file is None:
        csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiro_accounts.csv')
    
    if not os.path.exists(csv_file):
        return None
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_email = row.get('Email', row.get('email', ''))
            if row_email == email_addr:
                return row.get('Password', row.get('password', ''))
    return None


def automate_browser_login(playwright, verification_uri, email_addr, password, user_code):
    """Automate the full browser login flow."""
    print(f"[*] Browser: Opening {verification_uri}")
    
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = context.new_page()
    
    try:
        # Open verification URI
        page.goto(verification_uri, wait_until='networkidle', timeout=30000)
        time.sleep(3)
        
        # Dismiss cookie banner
        try:
            accept_btn = page.locator('[data-id="awsccc-cb-btn-accept"]')
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                time.sleep(1)
        except:
            pass
        
        # Enter email
        print("[*] Browser: Entering email...")
        email_input = page.locator('input[id="resolver_input_field"], input[name="username"], input[type="email"]').first
        email_input.wait_for(timeout=15000)
        email_input.fill(email_addr)
        time.sleep(1)
        
        email_submit_time = time.time()
        
        # Click Next
        next_btn = page.locator('[data-testid="test-primary-button"]').first
        next_btn.wait_for(timeout=10000)
        next_btn.click()
        time.sleep(4)
        
        # Enter password
        print("[*] Browser: Entering password...")
        password_input = page.locator('input[type="password"]').first
        password_input.wait_for(timeout=10000)
        password_input.fill(password)
        time.sleep(1)
        
        continue_btn = page.locator('button:has-text("Continue")').first
        continue_btn.click()
        time.sleep(5)
        print("[*] Browser: Password submitted, waiting for OTP...")
        
        # Get OTP from Gmail
        otp = get_otp_from_gmail(timeout=120, after_timestamp=email_submit_time)
        
        if otp:
            print(f"[*] Browser: Found OTP: {otp}")
            
            otp_input = page.locator('input[placeholder="6-digit"], input[placeholder="Enter code"], input[name="code"], input[id="code"]').first
            try:
                otp_input.wait_for(timeout=10000)
                otp_input.fill(otp)
                time.sleep(1)
                
                continue_btn = page.locator('button:has-text("Continue")').first
                continue_btn.click()
                time.sleep(5)
                print("[*] Browser: OTP submitted")
            except Exception as e:
                print(f"[-] Browser: OTP submit error: {e}")
                page.keyboard.type(otp)
                time.sleep(1)
                page.keyboard.press('Enter')
                time.sleep(5)
                print("[*] Browser: OTP submitted via keyboard")
        else:
            print("[-] Browser: OTP not found!")
            page.screenshot(path='/tmp/kiro_otp_missing.png')
            browser.close()
            return False
        
        # Wait for authorization confirmation page
        time.sleep(3)
        page_content = page.content()
        
        if 'Authorization requested' in page_content or 'Confirm and continue' in page_content:
            print("[*] Browser: Authorization confirmation page...")
            
            if user_code in page_content:
                print(f"    Code matches: {user_code}")
            
            confirm_btn = page.locator('button:has-text("Confirm and continue")').first
            confirm_btn.wait_for(timeout=10000)
            confirm_btn.click()
            time.sleep(5)
            print("[+] Browser: Authorization confirmed! Token should be available now.")
        else:
            print("[*] Browser: No confirmation page - checking state...")
            print(f"    URL: {page.url}")
            page.screenshot(path='/tmp/kiro_state.png')
        
        # Wait a bit for the token to be available via API
        time.sleep(3)
        print("[+] Browser: Flow completed")
        browser.close()
        return True
        
    except Exception as e:
        print(f"[-] Browser: Error: {e}")
        page.screenshot(path='/tmp/kiro_error.png')
        browser.close()
        return False


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
                if poll_count % 60 == 0:
                    print(f"    [Poll #{poll_count}] Waiting... ({int(time.time()-start_time)}s)")
                time.sleep(interval)
                continue
            elif error_code == 'ExpiredTokenException':
                print(f"    [Poll #{poll_count}] Device code expired.")
                break
            elif error_code == 'InvalidGrantException':
                print(f"    [Poll #{poll_count}] Invalid grant - auth denied or code used.")
                break
            elif error_code == 'InvalidClientException':
                print(f"    [Poll #{poll_count}] Invalid client.")
                break
            else:
                print(f"    [Poll #{poll_count}] ERROR: {error_code}")
                time.sleep(interval)
                continue
        except Exception as e:
            print(f"    [Poll #{poll_count}] Unexpected: {e}")
            time.sleep(interval)
            continue
    
    print(f"    [Poll #{poll_count}] Timeout after {int(time.time()-start_time)}s")
    return None


def main():
    parser = argparse.ArgumentParser(description='Full Kiro CLI login flow')
    parser.add_argument('--email', required=True, help='Email for the AWS account')
    parser.add_argument('--password', default=None, help='Password (auto from CSV if not provided)')
    parser.add_argument('--output', default=None, help='Output token file')
    args = parser.parse_args()
    
    email_addr = args.email
    password = args.password or get_account_password(email_addr)
    
    if not password:
        print("ERROR: No password available for this account!")
        return 1
    
    print(f"[*] Starting full login flow for: {email_addr}")
    
    # Step 1: Register OIDC client
    print("[*] Step 1: Registering OIDC client...")
    sso_client = boto3.client('sso-oidc', region_name='us-east-1')
    reg = sso_client.register_client(clientName=CLIENT_NAME, clientType=CLIENT_TYPE)
    client_id = reg['clientId']
    client_secret = reg['clientSecret']
    print(f"    Client ID: {client_id}")
    
    # Step 2: Start device authorization
    print("[*] Step 2: Starting device authorization...")
    device = sso_client.start_device_authorization(
        clientId=client_id,
        clientSecret=client_secret,
        startUrl=START_URL
    )
    user_code = device['userCode']
    verification_uri = device['verificationUriComplete']
    device_code = device['deviceCode']
    interval = device['interval']
    expires_in = device['expiresIn']
    
    print(f"    User Code: {user_code}")
    print(f"    URI: {verification_uri}")
    print(f"    Expires in: {expires_in}s")
    
    # Step 3: Run browser automation in a separate thread
    import threading
    
    browser_done = threading.Event()
    browser_success = [False]
    
    def run_browser():
        with sync_playwright() as p:
            browser_success[0] = automate_browser_login(p, verification_uri, email_addr, password, user_code)
        browser_done.set()
    
    browser_thread = threading.Thread(target=run_browser, daemon=True)
    browser_thread.start()
    
    # Step 4: Poll for token while browser is running
    print("[*] Step 4: Polling for token (browser running in parallel)...")
    token_resp = poll_for_token(client_id, client_secret, device_code, interval, max_time=expires_in)
    
    if token_resp:
        print("[+] Token captured successfully!")
        token_data = {
            'email': email_addr,
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
        
        output_file = args.output or f"/tmp/kiro_token_{email_addr.replace('@', '_').replace('.', '_')}.json"
        with open(output_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"    Token saved to: {output_file}")
        
        # Also try to store in keyring for kiro-cli compatibility
        try:
            import keyring
            keyring.set_password('kirocli:odic:token', 'token', json.dumps(token_data))
            print("    Token also stored in keyring (kirocli:odic:token)")
        except Exception as e:
            print(f"    Could not store in keyring: {e} (not critical)")
        
        return 0
    else:
        print("[-] Failed to capture token")
        if not browser_done.is_set():
            browser_done.wait(timeout=30)
        return 1


if __name__ == '__main__':
    sys.exit(main())
