"""
Full pipeline: boto3 OIDC -> non-headless browser -> email -> name -> OTP -> confirm -> allow -> token -> panel import.
Uses Xvfb for display (non-headless mode to avoid AWS bot detection).
"""
import sys, os, time, uuid, threading, subprocess
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
        return True
    return False

def get_state(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
    return {
        'body': body or '',
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body,
        'onAllow': 'allow' in body,
        'onErr': 'err-837' in body,
        'onRateLimit': 'retry in 15 minutes' in body,
    }

def find_input(page, is_password=False):
    selectors = []
    if is_password:
        selectors = ['input[type="password"]:visible', 'input:visible']
    else:
        selectors = ['input:not([type="password"]):visible', 'input[type="email"]:visible', 'input[type="text"]:visible', 'input:visible']
    for sel in selectors:
        try:
            inp = page.locator(sel).first
            inp.wait_for(timeout=3000)
            if inp.is_visible():
                return inp
        except Exception:
            continue
    return None

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
        print("Usage: python3 full_flow_visible.py <email>")
        return
    
    email = sys.argv[1]
    name = email.split('@')[0]
    print(f"[*] Adding: {email}")
    
    # Start Xvfb
    xvfb = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1366x768x24'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
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
    
    print(f"[*] User Code: {user_code}")
    
    token_received = [None]
    
    def poll_token():
        deadline = time.time() + expires_in + 120
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
                    print(f"[!] Token poll: {err}")
                    return
                else:
                    continue
        print("[!] Token poll timed out")
    
    poll_thread = threading.Thread(target=poll_token, daemon=True)
    poll_thread.start()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--proxy-server=socks5://45.194.33.12:30001'],
                env={**os.environ, 'DISPLAY': ':99'}
            )
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768}
            )
            page = context.new_page()
            
            # Navigate to device page
            try:
                page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                          wait_until='commit', timeout=30000)
            except Exception:
                pass
            
            # Wait for page to render
            for i in range(20):
                time.sleep(1.0)
                body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
                if body and len(body) > 20:
                    break
            
            handle_cookies(page)
            
            # Click Continue on device page
            try:
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                print("  [+] Device Continue clicked")
            except Exception:
                print("  [!] Device Continue failed")
                state = get_state(page)
                if state['onRateLimit']:
                    print("[!] Rate limited")
                    page.close(); context.close(); browser.close(); xvfb.terminate()
                    return
            
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
                page.close(); context.close(); browser.close(); xvfb.terminate()
                return
            inp.click()
            inp.press('Control+a')
            inp.press('Backspace')
            inp.fill(email)
            inp.press('Enter')
            print("  [+] Email submitted")
            
            # Wait for next state
            for _ in range(15):
                time.sleep(1.0)
                state = get_state(page)
                if state['onName'] or state['onOtp'] or state['onErr'] or state['onRateLimit']:
                    break
            
            print(f"[*] After email: onName={state['onName']}, onOtp={state['onOtp']}, rateLimit={state['onRateLimit']}")
            
            if state['onRateLimit']:
                page.close(); context.close(); browser.close(); xvfb.terminate()
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
                    except Exception:
                        pass
                    print("  [+] Name submitted")
                
                for _ in range(20):
                    time.sleep(1.0)
                    state = get_state(page)
                    if state['onOtp'] or state['onErr'] or state['onRateLimit']:
                        break
                
                if state['onErr']:
                    print("[!] ERR-837 - retrying after 15s...")
                    time.sleep(15)
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
                    page.close(); context.close(); browser.close(); xvfb.terminate()
                    return
            
            # OTP
            if state['onOtp']:
                print("[*] Waiting for OTP email...")
                otp_arrival = time.time()
                
                otp = None
                for attempt in range(20):
                    time.sleep(6.0)
                    otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival - 120)
                    if otp:
                        break
                
                if not otp:
                    print("[*] Trying resend...")
                    try:
                        page.locator('button:has-text("Resend")').first.click(timeout=5000)
                        otp_arrival = time.time()
                        for attempt in range(10):
                            time.sleep(6.0)
                            otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival - 120)
                            if otp:
                                break
                    except Exception:
                        pass
                
                if otp:
                    print(f"  [+] OTP: {otp}")
                    inp = find_input(page)
                    if inp:
                        inp.click()
                        inp.fill(otp)
                        inp.press('Enter')
                        print("  [+] OTP submitted")
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
                else:
                    print("[!] No OTP received - aborting")
                    page.close(); context.close(); browser.close(); xvfb.terminate()
                    return
            
            page.close()
            context.close()
            browser.close()
    finally:
        xvfb.terminate()
        xvfb.wait()
    
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
