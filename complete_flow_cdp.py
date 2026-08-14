"""
Complete flow using Manus sandbox browser (CDP):
email -> name -> OTP -> confirm -> allow -> capture token -> import to panel
"""
import sys, os, time, uuid, threading
import boto3
from botocore.exceptions import ClientError
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

def safe_eval(page, js, default=None):
    try:
        return page.evaluate(js)
    except Exception:
        return default

def get_state(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
    return {
        'body': body or '',
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body,
        'onAllow': 'allow' in body,
        'onErr': 'err-837' in body,
        'onRateLimit': 'retry in' in body and ('minute' in body or 'minutes' in body),
        'onPassword': 'password' in body and 'continue' in body,
    }

def find_input(page):
    selectors = ['input:not([type="password"]):visible', 'input[type="email"]:visible', 'input[type="text"]:visible', 'input:visible']
    for sel in selectors:
        try:
            inp = page.locator(sel).first
            inp.wait_for(timeout=5000)
            if inp.is_visible():
                return inp
        except Exception:
            continue
    return None

def handle_cookies(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''")
    if body and ('cookie preferences' in body or 'essential cookies' in body):
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            try:
                page.locator('button:has-text("Accept")').first.click(timeout=3000)
            except Exception:
                pass
        time.sleep(3.0)

def add_to_panel(refresh_token, email):
    import requests
    session = requests.Session()
    resp = session.post("https://ourproxy.sryze.cc/api/auth/login",
                       json={"password": "7894561230"}, timeout=10)
    if not resp.ok:
        return False
    resp = session.post("https://ourproxy.sryze.cc/api/oauth/kiro/import",
                       json={
                           "refreshToken": refresh_token,
                           "region": "us-east-1",
                           "authMethod": "builder-id",
                           "startUrl": "https://view.awsapps.com/start",
                           "name": email
                       }, timeout=30)
    return resp.ok

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 complete_flow_cdp.py <email>")
        return
    
    email = sys.argv[1]
    name = email.split('@')[0]
    print(f"[*] Processing: {email}")
    
    # Register OIDC client
    client = boto3.client('sso-oidc', region_name='us-east-1')
    reg = client.register_client(
        clientName=f'kiro-{uuid.uuid4().hex[:8]}',
        clientType='public'
    )
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
    
    token_received = [None]
    
    def poll_token():
        deadline = time.time() + expires_in + 120
        while time.time() < deadline:
            time.sleep(interval)
            try:
                resp = client.create_token(
                    clientId=reg['clientId'],
                    clientSecret=reg['clientSecret'],
                    grantType='urn:ietf:params:oauth:grant-type:device_code',
                    deviceCode=device_code
                )
                token_received[0] = resp.get('refreshToken')
                print("[+] TOKEN RECEIVED!")
                return
            except ClientError as e:
                err = e.response['Error']['Code']
                if err in ('AuthorizationPendingException', 'SlowDownException'):
                    continue
                elif err in ('ExpiredTokenException', 'AccessDeniedException'):
                    print(f"[!] Token poll: {err}")
                    return
                else:
                    continue
    
    poll_thread = threading.Thread(target=poll_token, daemon=True)
    poll_thread.start()
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to device page
        try:
            page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                      wait_until='commit', timeout=60000)
        except Exception as e:
            print(f"Goto: {e}")
        
        # Wait for content
        for i in range(30):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
            if body and len(body) > 30 and 'forbidden' not in body.lower():
                break
        
        handle_cookies(page)
        
        # Click Continue on device page
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
            print("[+] Device Continue clicked")
        except Exception:
            print("[!] Device Continue failed")
        
        # Wait for email page
        for _ in range(15):
            time.sleep(1.0)
            handle_cookies(page)
            body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
            if body and 'email' in body:
                break
        
        # Fill email
        inp = find_input(page)
        if not inp:
            print("[!] No email input found")
            page.close(); context.close()
            poll_thread.join(timeout=5)
            return
        
        inp.click()
        inp.press('Control+a')
        inp.press('Backspace')
        inp.fill(email)
        inp.press('Enter')
        print("[+] Email submitted")
        
        # Wait for next state
        state = None
        for _ in range(20):
            time.sleep(1.0)
            state = get_state(page)
            if state['onName'] or state['onOtp'] or state['onErr'] or state['onRateLimit'] or state['onPassword']:
                break
        
        print(f"After email: onName={state['onName']}, onOtp={state['onOtp']}, onPassword={state['onPassword']}, err={state['onErr']}, rateLimit={state['onRateLimit']}")
        
        if state['onRateLimit']:
            print("[!] Rate limited")
            page.close(); context.close()
            poll_thread.join(timeout=5)
            return
        
        if state['onPassword']:
            print("[!] Account already exists - password page shown")
            page.close(); context.close()
            poll_thread.join(timeout=5)
            return
        
        # Name page
        if state['onName']:
            inp = find_input(page)
            if inp:
                inp.click()
                inp.type(name.title(), delay=100)
                time.sleep(1.0)
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    print("[+] Name submitted")
                except Exception:
                    pass
                
                # Wait for OTP
                for _ in range(20):
                    time.sleep(1.0)
                    state = get_state(page)
                    if state['onOtp'] or state['onErr'] or state['onRateLimit']:
                        break
                
                # Retry ERR-837 once
                if state['onErr']:
                    print("[!] ERR-837 - retrying...")
                    time.sleep(5)
                    inp = find_input(page)
                    if inp:
                        inp.click()
                        inp.type(name.title(), delay=100)
                        time.sleep(1.0)
                        try:
                            page.locator('button:has-text("Continue")').first.click(timeout=5000)
                        except Exception:
                            pass
                    for _ in range(20):
                        time.sleep(1.0)
                        state = get_state(page)
                        if state['onOtp'] or state['onErr'] or state['onRateLimit']:
                            break
                
                if state['onErr'] or state['onRateLimit']:
                    print(f"[!] Failed: err={state['onErr']}, rateLimit={state['onRateLimit']}")
                    page.close(); context.close()
                    poll_thread.join(timeout=5)
                    return
            
            # OTP
            if state['onOtp']:
                print("[*] Waiting for OTP email...")
                otp_arrival = time.time()
                
                otp = None
                for attempt in range(15):
                    time.sleep(6.0)
                    otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival - 120)
                    if otp:
                        break
                
                if not otp:
                    # Resend
                    try:
                        page.locator('button:has-text("Resend")').first.click(timeout=5000)
                        otp_arrival = time.time()
                        for attempt in range(8):
                            time.sleep(6.0)
                            otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival - 120)
                            if otp:
                                break
                    except Exception:
                        pass
                
                if otp:
                    print(f"[+] OTP: {otp}")
                    inp = find_input(page)
                    if inp:
                        inp.click()
                        inp.fill(otp)
                        inp.press('Enter')
                        print("[+] OTP submitted")
                        time.sleep(8.0)
                    
                    try:
                        page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                        print("[+] Confirm clicked")
                        time.sleep(8.0)
                    except Exception:
                        pass
                    
                    state = get_state(page)
                    if state['onAllow']:
                        try:
                            page.locator('button:has-text("Allow")').first.click(timeout=5000)
                            print("[+] Allow clicked - AUTH COMPLETE!")
                            time.sleep(10.0)
                        except Exception:
                            print("[!] Allow click failed")
                    else:
                        print(f"[*] After confirm: {state['body'][:100]}")
                else:
                    print("[!] No OTP received")
        
        page.close()
        context.close()
    
    # Wait for token
    print("[*] Waiting for token...")
    poll_thread.join(timeout=120)
    
    if token_received[0]:
        print("[+] Token captured!")
        if add_to_panel(token_received[0], email):
            print(f"[+] SUCCESS: {email} added to panel!")
            # Save to CSV
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiro_accounts.csv'), 'a') as f:
                f.write(f"{email},{time.strftime('%Y-%m-%d %H:%M:%S')},success,cdp\n")
            return True
        else:
            print("[!] Panel import failed")
            return False
    else:
        print("[!] Token not received")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
