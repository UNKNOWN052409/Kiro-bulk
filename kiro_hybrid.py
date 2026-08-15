#!/usr/bin/env python3
"""
Kiro AI Account Creator - Single Browser Session
Uses one Playwright browser instance with SOCKS5 proxy for the entire flow.
curl_cffi only used for OIDC registration (which doesn't hit TES).
"""

import uuid, secrets, hashlib, base64, time, random, re, json, sys
from urllib.parse import quote, urlparse, parse_qs
import subprocess
import socket
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import imaplib
import email as email_lib
import email.utils
from datetime import datetime, timezone

CALLBACK_PORT = 9997
SOCKS5_PORT = 10800
HTTP_PROXY_PORT = 8899
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcv eobi tfwh terw'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen',
               'Daniel', 'Matthew', 'Anthony', 'Mark', 'Donald', 'Steven', 'Andrew', 'Paul', 'Joshua', 'Kenneth']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott',
              'Wright', 'Lopez', 'Hill', 'Green', 'Adams', 'Baker', 'Gonzalez', 'Nelson', 'Carter', 'Mitchell']

CHROME_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def create_cffi_session():
    return cffi_requests.Session(
        impersonate='chrome124',
        proxy=f'http://127.0.0.1:{HTTP_PROXY_PORT}',
        timeout=60,
    )


def extract_otp():
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select('inbox')
        status, messages = mail.search(None, '(FROM "amazon")')
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        msg_ids = messages[0].split()
        for msg_id in reversed(msg_ids[-10:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            if 'amazon' not in msg.get('From', '').lower():
                continue
            try:
                msg_date = email.utils.parsedate_to_datetime(msg.get('Date', ''))
                age = (datetime.now(timezone.utc) - msg_date).total_seconds() if msg_date.tzinfo else 0
                if age > 300:
                    continue
            except:
                pass
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if 'html' in part.get_content_type():
                            body = re.sub(r'<[^>]+>', ' ', body)
                        m = re.search(r'\b(\d{6})\b', body)
                        if m:
                            otp = m.group(1)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                m = re.search(r'\b(\d{6})\b', body)
                if m:
                    otp = m.group(1)
            if otp:
                mail.logout()
                return otp
        mail.logout()
        return None
    except Exception as e:
        print(f"    [Gmail] Error: {e}")
        return None


def create_account():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email_addr = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    account_info = {
        'email': email_addr,
        'name': full_name,
        'password': password,
        'status': 'pending'
    }
    
    print(f"\n{'='*60}")
    print(f"Creating: {full_name} <{email_addr}>")
    print(f"Password: {password}")
    print(f"{'='*60}\n")
    
    # Ensure proxies are running
    for port, script in [(SOCKS5_PORT, 'socks5_bridge.py'), (HTTP_PROXY_PORT, 'proxy_wrapper_standalone.py')]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            subprocess.Popen(
                [sys.executable, f'/home/ubuntu/kiro-gen/{script}',
                 '--port', str(port), '--session', 'res-us'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            time.sleep(1)
            print(f"[Proxy] Started {script} on port {port}")
        except OSError:
            print(f"[Proxy] {script} already running on port {port}")
    
    # Register OIDC client via curl_cffi (Chrome TLS fingerprint)
    print("[1] Registering OIDC client via curl_cffi...")
    cffi_session = create_cffi_session()
    reg_data = {
        'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
        'clientType': 'public',
        'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
        'grantTypes': ['authorization_code', 'refresh_token'],
        'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
        'issuerUrl': 'https://view.awsapps.com/start'
    }
    reg_resp = cffi_session.post('https://oidc.us-east-1.amazonaws.com/client/register', json=reg_data)
    if reg_resp.status_code != 200:
        account_info['status'] = 'failed_register'
        cffi_session.close()
        return account_info
    client_id = reg_resp.json()['clientId']
    print(f"    Client ID: {client_id}")
    
    # PKCE
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    
    # Build authorize URL
    state = secrets.token_urlsafe(16)
    scopes = 'codewhisperer:completions codewhisperer:analysis codewhisperer:conversations'
    auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
                f'&client_id={client_id}'
                f'&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}'
                f'&scopes={quote(scopes)}'
                f'&state={state}'
                f'&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Single browser session for everything using Playwright + Stealth
    print("[2] Starting browser session with stealth...")
    oauth_code = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-infobars',
                '--enable-features=NetworkService',
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            # No proxy - direct connection test
        )
        page = context.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)
        
        # Navigate to authorize URL
        print("    Navigating to authorize...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=120000)
        print(f"    Page URL: {page.url[:100]}")
        
        # Step 3: Email
        print("[3] Submitting email...")
        email_submitted = False
        for i in range(30):
            time.sleep(2)
            try:
                email_input = page.locator('input[type="email"]').first
                if email_input.is_visible(timeout=2000):
                    email_input.click()
                    time.sleep(random.uniform(0.3, 0.7))
                    email_input.fill(email_addr)
                    time.sleep(random.uniform(0.5, 1.0))
                    
                    btn = page.locator('button:has-text("Continue")').first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        email_submitted = True
                        print(f"    Email submitted at {i*2}s")
                        time.sleep(5)
                        break
            except:
                pass
        
        if not email_submitted:
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_email.png')
            print("    [!] Email not submitted")
            account_info['status'] = 'failed_email'
            browser.close()
            return account_info
        
        # Step 4: Name
        print("[4] Submitting name...")
        name_submitted = False
        for i in range(45):
            time.sleep(2)
            try:
                text = page.inner_text('body')
                if 'enter your name' in text.lower():
                    print(f"    Name form detected at {i*2}s")
                    name_input = page.locator('input[type="text"]').first
                    if name_input.is_visible(timeout=3000):
                        name_input.click()
                        time.sleep(random.uniform(0.5, 1.0))
                        for char in full_name:
                            name_input.type(char, delay=random.uniform(50, 150))
                        time.sleep(random.uniform(0.5, 1.5))
                        
                        btn = page.locator('button:has-text("Continue")').first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            print(f"    Name submitted at {i*2}s")
                            name_submitted = True
                            time.sleep(5)
                            
                            # Check for TES error - be specific
                            after_text = page.inner_text('body')
                            if 'err-837' in after_text.lower() or 'unexpected error' in after_text.lower() and 'sign in again' in after_text.lower():
                                print("    [!] TES blocked name submission")
                                page.screenshot(path='/home/ubuntu/kiro-gen/debug_tes_name.png')
                                account_info['status'] = 'failed_tes_name'
                                browser.close()
                                return account_info
                            # If we see password form or OTP form, name was submitted successfully
                            if 'password' in after_text.lower() or 'code' in after_text.lower():
                                print("    Name submission SUCCESS - moving to next step")
                            break
            except Exception as e:
                if i == 44:
                    print(f"    [!] Name error: {e}")
        
        if not name_submitted:
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_name.png')
            print("    [!] Name not submitted")
            account_info['status'] = 'failed_name'
            browser.close()
            return account_info
        
        # Step 5: OTP
        print("[5] Handling OTP...")
        otp_detected = False
        for i in range(60):
            time.sleep(2)
            try:
                text = page.inner_text('body')
                otp_keywords = ['one-time', 'otp', 'verification code', 'enter the code', 'sent to', 'enter a code']
                if any(kw in text.lower() for kw in otp_keywords):
                    otp_detected = True
                    print(f"    OTP form detected at {i*2}s")
                    
                    # Get OTP from Gmail
                    otp_code = None
                    for j in range(15):
                        otp_code = extract_otp()
                        if otp_code:
                            break
                        time.sleep(3)
                    
                    if otp_code:
                        print(f"    OTP: {otp_code}")
                        # Fill OTP
                        for sel in ['input[inputmode="numeric"]', 'input[type="text"]']:
                            inputs = page.locator(sel).all()
                            filled = False
                            for inp in inputs:
                                if inp.is_visible() and 'password' not in (inp.get_attribute('type') or ''):
                                    try:
                                        inp.fill(otp_code)
                                        time.sleep(0.3)
                                        btn = page.locator('button:has-text("Continue"), button:has-text("Verify"), button[type="submit"]').first
                                        if btn.is_visible(timeout=1000):
                                            btn.click()
                                            filled = True
                                            print("    OTP submitted!")
                                            time.sleep(3)
                                            break
                                    except:
                                        continue
                            if filled:
                                break
                    else:
                        print("    [!] OTP not found")
                        account_info['status'] = 'failed_otp_extract'
                        browser.close()
                        return account_info
                    break
            except Exception as e:
                if i == 29:
                    print(f"    [!] OTP error: {e}")
        
        if not otp_detected:
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_otp.png')
            print("    [!] OTP form not detected")
            account_info['status'] = 'failed_otp'
            browser.close()
            return account_info
        
        # Step 6: Password
        print("[6] Setting password...")
        pw_submitted = False
        for i in range(30):
            time.sleep(2)
            try:
                text = page.inner_text('body')
                if 'password' in text.lower() and ('create' in text.lower() or 'set' in text.lower()):
                    print(f"    Password form detected at {i*2}s")
                    pw_inputs = page.locator('input[type="password"]').all()
                    visible_pw = [inp for inp in pw_inputs if inp.is_visible()]
                    if visible_pw:
                        visible_pw[0].fill(password)
                        time.sleep(0.3)
                        if len(visible_pw) >= 2:
                            visible_pw[1].fill(password)
                            time.sleep(0.3)
                        btn = page.locator('button:has-text("Create"), button[type="submit"], button:has-text("Continue")').first
                        if btn.is_visible(timeout=1000):
                            btn.click()
                            pw_submitted = True
                            print("    Password submitted!")
                            time.sleep(5)
                            break
            except:
                pass
        
        if not pw_submitted:
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_pw.png')
            print("    [!] Password form not detected")
            account_info['status'] = 'failed_password'
            browser.close()
            return account_info
        
        # Step 7: Check for OAuth code in redirect
        final_url = page.url
        print(f"    Final URL: {final_url[:100]}")
        
        for i in range(10):
            time.sleep(2)
            final_url = page.url
            code_match = re.search(r'code=([A-Za-z0-9._~\-]+)', final_url)
            if code_match:
                oauth_code = code_match.group(1)
                break
        
        browser.close()
    
    cffi_session.close()
    
    if oauth_code:
        print(f"    OAuth code: {oauth_code[:30]}...")
        account_info['oauth_code'] = oauth_code
        account_info['code_verifier'] = code_verifier
        account_info['client_id'] = client_id
        account_info['status'] = 'success'
        
        # Exchange code for token
        print("[7] Exchanging code for token...")
        token_session = cffi_requests.Session(
            impersonate='chrome124',
            proxy=f'http://127.0.0.1:{HTTP_PROXY_PORT}',
            timeout=30,
        )
        token_resp = token_session.post('https://oidc.us-east-1.amazonaws.com/token', json={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'code': oauth_code,
            'redirect_uri': f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback',
            'code_verifier': code_verifier
        })
        if token_resp.status_code == 200:
            token_data = token_resp.json()
            account_info['access_token'] = token_data.get('access_token', '')
            account_info['refresh_token'] = token_data.get('refresh_token', '')
            account_info['id_token'] = token_data.get('id_token', '')
            print(f"    ✓ Token captured!")
        else:
            print(f"    [!] Token exchange failed: {token_resp.text[:200]}")
            account_info['status'] = 'partial'
        token_session.close()
    else:
        print(f"    [!] No OAuth code, final URL: {final_url[:200]}")
        account_info['status'] = 'no_oauth_code'
    
    return account_info


if __name__ == '__main__':
    result = create_account()
    print(f"\n{'='*60}")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"{'='*60}")
    
    with open('/home/ubuntu/kiro-gen/last_account.json', 'w') as f:
        json.dump(result, f, indent=2)
    print("Saved to last_account.json")
