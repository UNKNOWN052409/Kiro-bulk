#!/usr/bin/env python3
"""Test without proxy but with system Chromium channel and user-data-dir"""

import uuid, secrets, hashlib, base64, time, random, re, json
from urllib.parse import quote
import imaplib
import email as email_lib
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcv eobi tfwh terw'
DIRECTORY_ID = 'd-9067642ac7'
FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson']
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'

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
        for msg_id in reversed(msg_ids[-5:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK': continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            if 'amazon' not in msg.get('From', '').lower(): continue
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if 'html' in part.get_content_type(): body = re.sub(r'<[^>]+>', ' ', body)
                        m = re.search(r'\b(\d{6})\b', body)
                        if m: otp = m.group(1); break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                m = re.search(r'\b(\d{6})\b', body)
                if m: otp = m.group(1)
            if otp:
                mail.logout()
                return otp
        mail.logout()
        return None
    except Exception as e:
        print(f"    Gmail: {e}")
        return None

def main():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email_addr = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    print(f"Creating: {full_name} <{email_addr}>")
    
    with sync_playwright() as p:
        # Use system Chromium with persistent context (real profile)
        context = p.chromium.launch_persistent_context(
            '/tmp/chrome-profile-test',
            channel='chromium',
            headless=True,
            viewport={'width': 1920, 'height': 1080},
            user_agent=CHROME_UA,
            locale='en-US',
            timezone_id='America/New_York',
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(30000)
        
        # Register OIDC client
        print("[1] OIDC register...")
        from curl_cffi import requests as cffi_requests
        cffi_session = cffi_requests.Session(impersonate='chrome124', timeout=30)
        reg = cffi_session.post('https://oidc.us-east-1.amazonaws.com/client/register', json={
            'clientName': f'kiro-test-{uuid.uuid4().hex[:8]}',
            'clientType': 'public',
            'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
            'grantTypes': ['authorization_code', 'refresh_token'],
            'redirectUris': ['http://127.0.0.1:9997/oauth/callback'],
            'issuerUrl': 'https://view.awsapps.com/start'
        })
        client_id = reg.json()['clientId']
        print(f"    Client: {client_id}")
        
        # Navigate
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
        auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
                    f'&client_id={client_id}'
                    f'&redirect_uri={quote("http://127.0.0.1:9997/oauth/callback")}'
                    f'&scopes={quote("codewhisperer:completions codewhisperer:analysis codewhisperer:conversations")}'
                    f'&state={secrets.token_urlsafe(16)}'
                    f'&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        
        print("[2] Navigate...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=90000)
        print(f"    URL: {page.url[:100]}")
        
        # Wait for SPA to redirect to signin page
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in page.url:
                print(f"    Redirected to signin at {i}s")
                break
        
        time.sleep(3)
        print(f"    Final URL: {page.url[:120]}")
        
        # Email
        print("[3] Email...")
        try:
            # Wait for navigation to complete
            time.sleep(5)
            print(f"    Current URL: {page.url[:80]}")
            
            # Try multiple selectors for email input
            email_input = None
            for sel in ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="email"]', 'input']:  
                try:
                    email_input = page.locator(sel).first
                    if email_input.is_visible(timeout=3000):
                        break
                    email_input = None
                except:
                    email_input = None
            
            if not email_input:
                # Take screenshot and dump page state
                page.screenshot(path='/home/ubuntu/kiro-gen/debug_email_noproxy.png')
                print(f"    Page text: {page.inner_text('body')[:300]}")
                raise Exception("Email input not found")
            
            email_input.fill(email_addr)
            time.sleep(1)
            # Try clicking Continue button or pressing Enter
            btn = page.locator('button:has-text("Continue")').first
            if btn.is_visible(timeout=3000):
                btn.click()
            else:
                page.keyboard.press('Enter')
            print("    Email submitted")
            time.sleep(5)
        except Exception as e:
            print(f"    [!] Email: {e}")
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_email_noproxy.png')
            context.close()
            return
        
        # Name
        print("[4] Name...")
        try:
            text = page.inner_text('body')
            print(f"    Page text: {text[:200]}")
            if 'enter your name' in text.lower():
                name_input = page.locator('input[type="text"]').first
                name_input.wait_for(state='visible', timeout=10000)
                for char in full_name:
                    name_input.type(char, delay=random.uniform(50, 100))
                time.sleep(1)
                page.locator('button:has-text("Continue")').first.click()
                print("    Name submitted")
                time.sleep(5)
                
                # Check result
                text2 = page.inner_text('body')
                if 'err-837' in text2.lower():
                    print("    [!] ERR-837")
                elif 'Enter your' in text2 or 'verify' in text2.lower() or 'code' in text2.lower():
                    print("    [✓] Name OK - moved to next step")
                else:
                    print(f"    [?] Page text: {text2[:200]}")
            else:
                print(f"    [!] Name form not found. Text: {text[:100]}")
        except Exception as e:
            print(f"    [!] Name: {e}")
        
        page.screenshot(path='/home/ubuntu/kiro-gen/debug_final_noproxy.png')
        context.close()

if __name__ == '__main__':
    main()
