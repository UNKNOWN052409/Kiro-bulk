"""
Token capture via boto3 OIDC with browser automation - v3.
Added robust error handling for navigation issues.
"""
import sys, os, time, re, uuid, threading
import boto3
from botocore.exceptions import ClientError
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

def safe_evaluate(page, js):
    """Safely evaluate JS, returning None on navigation errors."""
    try:
        return page.evaluate(js)
    except Exception:
        return None

def handle_cookies(page):
    body = safe_evaluate(page, "document.body ? document.body.innerText.toLowerCase() : ''")
    if body and ('cookie preferences' in body or 'essential cookies' in body):
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            try:
                page.locator('button:has-text("Accept")').first.click(timeout=3000)
            except Exception:
                pass
        time.sleep(5.0)
        return True
    return False

def get_state(page):
    body = safe_evaluate(page, "document.body ? document.body.innerText.toLowerCase() : ''")
    if body is None:
        time.sleep(3.0)
        body = safe_evaluate(page, "document.body ? document.body.innerText.toLowerCase() : ''")
    body = body or ''
    return {
        'body': body,
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body,
        'onAllow': 'allow' in body,
        'onErr': 'err-837' in body,
        'onRateLimit': 'retry in 15 minutes' in body,
    }

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
    if resp.ok:
        return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 token_capture_poll3.py <email>")
        return
    
    email = sys.argv[1]
    name = email.split('@')[0]
    print(f"[*] Adding: {email}")
    
    # Register OIDC client
    client = boto3.client('sso-oidc', region_name='us-east-1')
    reg = client.register_client(
        clientName=f'kiro-{uuid.uuid4().hex[:8]}',
        clientType='public'
    )
    client_id = reg['clientId']
    client_secret = reg['clientSecret']
    
    device = client.start_device_authorization(
        clientId=client_id,
        clientSecret=client_secret,
        startUrl='https://view.awsapps.com/start'
    )
    user_code = device['userCode']
    device_code = device['deviceCode']
    interval = device['interval']
    expires_in = device['expiresIn']
    
    print(f"[*] User Code: {user_code} (expires in {expires_in}s)")
    
    token_received = [None]
    
    def poll_token():
        deadline = time.time() + expires_in + 60  # Extra buffer
        while time.time() < deadline:
            time.sleep(interval)
            try:
                resp = client.create_token(
                    clientId=client_id,
                    clientSecret=client_secret,
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
                    print(f"[!] Token poll failed: {err}")
                    return
                else:
                    continue
        print("[!] Token poll timed out")
    
    poll_thread = threading.Thread(target=poll_token, daemon=True)
    poll_thread.start()
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                      wait_until='domcontentloaded', timeout=30000)
        except Exception:
            try:
                page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                          wait_until='commit', timeout=30000)
            except Exception:
                pass
        
        time.sleep(5.0)
        handle_cookies(page)
        
        # Click Continue on device page
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception:
            pass
        
        # Wait for email page to load
        for _ in range(15):
            time.sleep(1.0)
            body = safe_evaluate(page, "document.body ? document.body.innerText.toLowerCase() : ''")
            if body and 'email' in body:
                break
        
        handle_cookies(page)
        
        # Fill email
        inp = page.locator('input:not([type="password"]):visible').first
        inp.click()
        inp.press('Control+a')
        inp.press('Backspace')
        inp.fill(email)
        inp.press('Enter')
        
        # Wait for navigation
        time.sleep(10.0)
        handle_cookies(page)
        
        state = get_state(page)
        print(f"[*] After email: onName={state['onName']}, onOtp={state['onOtp']}, rateLimit={state['onRateLimit']}")
        
        # Rate limit check
        if state['onRateLimit']:
            print("[!] Rate limited - aborting, try again later")
            page.close(); context.close()
            return
        
        # Name
        if state['onName']:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.type(name.title(), delay=100)
            time.sleep(1.0)
            try:
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
            except Exception:
                pass
            
            # Wait for navigation
            for _ in range(15):
                time.sleep(1.0)
                state = get_state(page)
                if state['onOtp'] or state['onErr'] or state['onRateLimit']:
                    break
            
            if state['onErr']:
                print("[!] ERR-837 - retrying after 15s...")
                time.sleep(15)
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.type(name.title(), delay=100)
                time.sleep(1.0)
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                except Exception:
                    pass
                for _ in range(15):
                    time.sleep(1.0)
                    state = get_state(page)
                    if state['onOtp'] or state['onErr'] or state['onRateLimit']:
                        break
            
            if state['onErr'] or state['onRateLimit']:
                print(f"[!] Failed: err={state['onErr']}, rateLimit={state['onRateLimit']}")
                print(f"[*] Body: {state['body'][:200]}")
                page.close(); context.close()
                return
            print(f"[*] After name: onOtp={state['onOtp']}")
        
        # OTP
        if state['onOtp']:
            print("[*] Waiting for OTP email...")
            otp_arrival = time.time()
            
            otp = None
            for attempt in range(15):
                time.sleep(8.0)
                otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival - 60)
                if otp:
                    break
                if attempt % 3 == 0:
                    print(f"  [*] Attempt {attempt+1}/15 - waiting for email...")
            
            if not otp:
                # Try resend
                print("[*] Trying resend...")
                try:
                    page.locator('button:has-text("Resend")').first.click(timeout=5000)
                    otp_arrival = time.time()
                    for attempt in range(8):
                        time.sleep(8.0)
                        otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival - 60)
                        if otp:
                            break
                except Exception:
                    pass
            
            if otp:
                print(f"  [+] OTP: {otp}")
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.fill(otp)
                inp.press('Enter')
                time.sleep(8.0)
                
                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    print("  [+] Confirm clicked")
                    time.sleep(8.0)
                except Exception:
                    pass
                
                state = get_state(page)
                if state['onAllow']:
                    try:
                        page.locator('button:has-text("Allow")').first.click(timeout=5000)
                        print("  [+] Allow clicked")
                        time.sleep(10.0)
                        print("[+] Browser auth complete!")
                    except Exception:
                        print("[!] Allow click failed")
                elif token_received[0]:
                    print("[+] Token received before Allow click!")
            else:
                print("[!] No OTP - aborting")
                page.close(); context.close()
                return
        elif token_received[0]:
            print("[+] Token already received!")
        else:
            print("[!] Unknown state - body:", state['body'][:200])
        
        page.close()
        context.close()
    
    # Wait for token
    print("[*] Waiting for token...")
    poll_thread.join(timeout=120)
    
    if token_received[0]:
        print("[+] Token captured!")
        if add_to_panel(token_received[0], email):
            print(f"[+] SUCCESS: {email} added to panel!")
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
