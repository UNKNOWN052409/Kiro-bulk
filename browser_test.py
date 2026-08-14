"""
Browser-based Kiro AI account creation WITHOUT proxy.
Tests the full flow to confirm it works.
"""

import uuid, secrets, hashlib, base64, time, random, re, json, threading, http.server
from urllib.parse import quote, urlparse, parse_qs
from playwright.sync_api import sync_playwright


CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UAMOBILE = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott']


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured_code = None
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        CallbackHandler.captured_code = params.get('code', [None])[0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
    def log_message(self, format, *args):
        pass


def extract_otp():
    import imaplib, email as email_lib
    email_user = 'anshika31618@gmail.com'
    email_pass = 'hlcv eobi tfwh terw'
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select('inbox')
        status, messages = mail.search(None, '(FROM "amazon.com" OR FROM "no-reply@amazon.com")')
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        msg_ids = messages[0].split()
        for msg_id in reversed(msg_ids[-5:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            from_addr = msg.get('From', '')
            if 'amazon' not in from_addr.lower():
                continue
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if ct == 'text/html':
                            body = re.sub(r'<[^>]+>', ' ', body)
                        match = re.search(r'\b(\d{6})\b', body)
                        if match:
                            otp = match.group(1)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                match = re.search(r'\b(\d{6})\b', body)
                if match:
                    otp = match.group(1)
            if otp:
                mail.logout()
                return otp
        mail.logout()
        return None
    except Exception as e:
        print(f"    Gmail error: {e}")
        return None


def main():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    print(f"Creating: {full_name} <{email}>")
    print(f"Password: {password}")
    print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UAMOBILE,
            locale='en-US',
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        # Track API calls
        api_responses = []
        def on_response(response):
            url = response.url
            if '/api/execute' in url:
                try:
                    body = response.json()
                    step = body.get('stepId', '')
                    api_responses.append({'step': step, 'url': url[:80], 'status': response.status})
                    print(f"    [API] step={step}, status={response.status}")
                except:
                    pass
        
        page.on('response', on_response)
        
        # First register OIDC client to get the authorize URL
        print("[0] Registering OIDC client...")
        import requests as req
        reg_resp = req.post(f'https://oidc.us-east-1.amazonaws.com/client/register', json={
            'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
            'clientType': 'public',
            'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
            'grantTypes': ['authorization_code', 'refresh_token'],
            'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
            'issuerUrl': 'https://view.awsapps.com/start'
        }, timeout=10)
        client_id = reg_resp.json()['clientId']
        print(f"    Client ID: {client_id}")
        
        # Generate code challenge
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()
        
        # Navigate to OIDC authorize
        print("[1] Navigating to OIDC authorize...")
        auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
                    f'&client_id={client_id}'
                    f'&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}'
                    f'&scopes={quote("codewhisperer:completions codewhisperer:analysis codewhisperer:conversations")}'
                    f'&state={secrets.token_urlsafe(16)}'
                    f'&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)
        print(f"    URL: {page.url}")
        
        # Wait for email form
        print("[2] Waiting for email form...")
        email_submitted = False
        for i in range(30):
            if email_submitted:
                break
            time.sleep(2)
            try:
                email_input = page.locator('input[type="email"]').first
                if email_input.is_visible(timeout=1000):
                    print(f"    Email form ready at {i*2}s!")
                    try:
                        email_input.click()
                        time.sleep(0.3)
                        email_input.fill(email)
                        time.sleep(0.5)
                        print(f"    Email filled: {email}")
                        # Try multiple button selectors
                        btn = None
                        for sel in ['button:has-text("Continue")', 'button[type="submit"]', 'input[type="submit"]']:
                            try:
                                btn = page.locator(sel).first
                                if btn.is_visible(timeout=1000):
                                    btn.click()
                                    email_submitted = True
                                    print(f"    Email submitted (clicked {sel})!")
                                    break
                            except:
                                pass
                    except Exception as e:
                        print(f"    [!] Fill/click error: {e}")
                        # Try JavaScript approach
                        try:
                            page.evaluate(f"""
                                const inputs = document.querySelectorAll('input[type="email"]');
                                for (const inp of inputs) {{
                                    if (inp.offsetParent !== null) {{
                                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                        setter.call(inp, '{email}');
                                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        break;
                                    }}
                                }}
                                const buttons = document.querySelectorAll('button, input[type="submit"]');
                                for (const b of buttons) {{
                                    if (b.offsetParent !== null && (b.textContent.includes('Continue') || b.type === 'submit')) {{
                                        b.click();
                                        break;
                                    }}
                                }}
                            """)
                            email_submitted = True
                            print("    Email submitted via JS!")
                        except Exception as e2:
                            print(f"    [!] JS error: {e2}")
                    if email_submitted:
                        time.sleep(2)  # Wait for redirect to start
                        break
            except Exception as e:
                pass
        
        if not email_submitted:
            print("    [!] Email form not found!")
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_email.png')
            print(f"    URL: {page.url}")
            print(f"    Body text: {page.inner_text('body')[:200]}")
            browser.close()
            return
        
        # Wait for name form (SPA navigates without URL change)
        print("[3-4] Waiting for name form...")
        name_submitted = False
        for i in range(60):
            if name_submitted:
                break
            time.sleep(2)
            current_url = page.url
            print(f"    [{i}] URL: {current_url[:80]}")
            try:
                # Always try to detect name form regardless of URL
                text = page.inner_text('body')
                if 'enter your name' in text.lower():
                    print(f"    Name form detected! Text: {text[:80]}")
                    
                    # Use Playwright's native fill - works with React
                    try:
                        # Try to find the name input using different selectors
                        name_input = None
                        for sel in ['input[placeholder*="name" i]', 'input[name="name"]', 'input[aria-label*="name" i]', 'input[type="text"]', 'input:not([type])']:
                            try:
                                inp = page.locator(sel).first
                                if inp.is_visible(timeout=2000):
                                    name_input = inp
                                    print(f"    Found name input with selector: {sel}")
                                    break
                            except:
                                pass
                        
                        if name_input:
                            name_input.click()
                            time.sleep(0.3)
                            name_input.fill(full_name)
                            time.sleep(0.5)
                            print(f"    Name filled: {full_name}")
                            
                            # Click continue button
                            btn_clicked = False
                            for sel in ['button:has-text("Continue")', 'button[type="submit"]']:
                                try:
                                    btn = page.locator(sel).first
                                    if btn.is_visible(timeout=1000):
                                        btn.click()
                                        btn_clicked = True
                                        print(f"    Clicked {sel}")
                                        break
                                except:
                                    pass
                            
                            if btn_clicked:
                                print(f"    Name '{full_name}' submitted at {i*2}s!")
                                # Wait to check for ERR-837 or success
                                time.sleep(3)
                                # Check if ERR-837 appeared
                                after_text = page.inner_text('body')
                                if 'err-837' in after_text.lower():
                                    print("    [!] ERR-837 detected - retrying...")
                                    time.sleep(2)
                                    # Dismiss error and retry
                                    try:
                                        close_btn = page.locator('button[aria-label*="close" i], .close, [data-testid*="close"]').first
                                        close_btn.click()
                                    except:
                                        pass
                                    # Refill and resubmit
                                    try:
                                        name_input.fill(full_name)
                                        time.sleep(0.3)
                                        for sel in ['button:has-text("Continue")', 'button[type="submit"]']:
                                            try:
                                                btn = page.locator(sel).first
                                                if btn.is_visible(timeout=1000):
                                                    btn.click()
                                                    print("    Retried name submission")
                                                    break
                                            except:
                                                pass
                                    except:
                                        pass
                                else:
                                    name_submitted = True
                                    print(f"    Name submission SUCCESS at {i*2}s!")
                                    time.sleep(3)
                            else:
                                print("    [!] Continue button not found")
                        else:
                            print("    [!] Name input not found")
                    except Exception as e:
                        print(f"    [!] Name fill error: {e}")
                elif i > 5:
                    # After 10s, log what's on the page
                    if i == 6:
                        print(f"    Body text: {text[:200]}")
            except Exception as e:
                print(f"    [!] Error at {i*2}s: {e}")
        
        if not name_submitted:
            print("    [!] Name form not found!")
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_name.png')
            print(f"    URL: {page.url}")
            browser.close()
            return
        
        # Wait for OTP form
        print("[5] Waiting for OTP form...")
        otp_submitted = False
        for i in range(30):
            time.sleep(2)
            try:
                text = page.inner_text('body')
                # Broad detection for OTP/verification code form
                otp_detected = ('one-time' in text.lower() or 
                               'otp' in text.lower() or 
                               'verification code' in text.lower() or
                               'verify' in text.lower() or
                               'enter the code' in text.lower() or
                               'sent to' in text.lower() or
                               ('code' in text.lower() and 'email' in text.lower()))
                if otp_detected:
                    print(f"    OTP form detected at {i*2}s")
                    # Get OTP from Gmail
                    otp = None
                    for j in range(20):
                        otp = extract_otp()
                        if otp:
                            break
                        time.sleep(3)
                    
                    if otp:
                        print(f"    OTP: {otp}")
                        otp_inputs = page.locator('input[type="text"], input[inputmode="numeric"]').all()
                        for inp in otp_inputs:
                            if inp.is_visible():
                                inp.fill(otp)
                                time.sleep(0.3)
                                page.locator('button:has-text("Continue"), button[type="submit"], button:has-text("Verify")').first.click()
                                otp_submitted = True
                                print("    OTP submitted!")
                                break
                    if otp_submitted:
                        break
            except:
                pass
        
        # Wait for password form
        print("[6] Waiting for password form...")
        pw_submitted = False
        for i in range(30):
            time.sleep(2)
            try:
                text = page.inner_text('body')
                if 'password' in text.lower() and 'create' in text.lower():
                    print(f"    Password form detected at {i*2}s")
                    pw_inputs = page.locator('input[type="password"]').all()
                    if len(pw_inputs) >= 2:
                        pw_inputs[0].fill(password)
                        time.sleep(0.2)
                        pw_inputs[1].fill(password)
                        time.sleep(0.3)
                        page.locator('button:has-text("Create"), button[type="submit"]').first.click()
                        pw_submitted = True
                        print("    Password submitted!")
                        break
            except:
                pass
        
        print(f"\n[FINAL] pw_submitted={pw_submitted}")
        print(f"    URL: {page.url}")
        print(f"    API calls captured: {len(api_responses)}")
        for r in api_responses:
            print(f"      step={r['step']}, status={r['status']}")
        
        page.screenshot(path='/home/ubuntu/kiro-gen/final_state.png')
        browser.close()
    
    print("Done!")


if __name__ == '__main__':
    main()
