"""
Batch add accounts to panel with 3-minute rate-limit wait between attempts.
"""
import sys, os, time, uuid, random, string, threading, subprocess
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
    }

def find_input(page):
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
    return resp.ok

def process_account(email, xvfb):
    name = email.split('@')[0]
    print(f"[*] Processing: {email}")
    
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
                print(f"[+] TOKEN RECEIVED for {email}!")
                return
            except ClientError as e:
                err = e.response['Error']['Code']
                if err in ('AuthorizationPendingException', 'SlowDownException'):
                    continue
                elif err in ('ExpiredTokenException', 'AccessDeniedException'):
                    return
                else:
                    continue
    
    poll_thread = threading.Thread(target=poll_token, daemon=True)
    poll_thread.start()
    
    result = {'success': False, 'email': email}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            env={**os.environ, 'DISPLAY': ':99'}
        )
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()
        
        try:
            # Navigate
            try:
                page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                          wait_until='commit', timeout=30000)
            except Exception:
                pass
            
            # Wait for render
            for i in range(20):
                time.sleep(1.0)
                body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
                if body and len(body) > 20:
                    break
            
            # Handle cookies
            handle_cookies(page)
            
            # Click Continue on device page
            try:
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
            except Exception:
                pass
            
            # Wait for email page
            for _ in range(15):
                time.sleep(1.0)
                body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
                if body and 'email' in body:
                    break
            
            # Fill email
            inp = find_input(page)
            if not inp:
                print(f"[!] No email input for {email}")
                page.close(); context.close(); browser.close()
                return result
            
            inp.click()
            inp.press('Control+a')
            inp.press('Backspace')
            inp.fill(email)
            inp.press('Enter')
            
            # Wait for next state
            state = None
            for _ in range(15):
                time.sleep(1.0)
                state = get_state(page)
                if state['onName'] or state['onOtp'] or state['onErr'] or state['onRateLimit']:
                    break
            
            if not state or state['onRateLimit']:
                print(f"[!] Rate limited for {email} - aborting")
                result['rate_limited'] = True
                page.close(); context.close(); browser.close()
                return result
            
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
                
                # Wait for OTP
                for _ in range(20):
                    time.sleep(1.0)
                    state = get_state(page)
                    if state['onOtp'] or state['onErr'] or state['onRateLimit']:
                        break
                
                # Retry ERR-837 once
                if state['onErr']:
                    print(f"[!] ERR-837 for {email} - waiting 3min and retrying...")
                    time.sleep(180)  # 3 minute wait
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
                    print(f"[!] Failed for {email}: err={state['onErr']}, rateLimit={state['onRateLimit']}")
                    page.close(); context.close(); browser.close()
                    return result
            
            # OTP
            if state['onOtp']:
                print(f"[*] Waiting for OTP for {email}...")
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
                    inp = find_input(page)
                    if inp:
                        inp.click()
                        inp.fill(otp)
                        inp.press('Enter')
                        time.sleep(8.0)
                    
                    try:
                        page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                        time.sleep(8.0)
                    except Exception:
                        pass
                    
                    state = get_state(page)
                    if state['onAllow']:
                        try:
                            page.locator('button:has-text("Allow")').first.click(timeout=5000)
                            time.sleep(10.0)
                            print(f"[+] Auth complete for {email}")
                        except Exception:
                            pass
                else:
                    print(f"[!] No OTP for {email}")
                    page.close(); context.close(); browser.close()
                    return result
            
            page.close()
            context.close()
            browser.close()
        
        except Exception as e:
            print(f"[!] Error processing {email}: {e}")
            try:
                page.close(); context.close(); browser.close()
            except Exception:
                pass
    
    # Wait for token
    poll_thread.join(timeout=60)
    
    if token_received[0]:
        if add_to_panel(token_received[0], email):
            print(f"[+] SUCCESS: {email} added to panel!")
            result['success'] = True
        else:
            print(f"[!] Panel import failed for {email}")
    else:
        print(f"[!] No token for {email}")
    
    return result

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

def generate_email():
    """Generate a random havenhaus.in email."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(10)) + '@havenhaus.in'

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    
    # Start Xvfb once
    xvfb = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1366x768x24'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    # Read existing accounts from CSV
    existing_emails = set()
    csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiro_accounts.csv')
    if os.path.exists(csv_file):
        with open(csv_file) as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) > 1 and '@' in parts[1]:
                    existing_emails.add(parts[1])
    
    print(f"[*] Target: {count} accounts, existing: {len(existing_emails)}")
    
    success_count = 0
    fail_count = 0
    
    for i in range(count):
        # Generate a unique email
        while True:
            email = generate_email()
            if email not in existing_emails:
                break
        
        print(f"\n{'='*50}")
        print(f"[*] Attempt {i+1}/{count}: {email}")
        
        result = process_account(email, xvfb)
        
        if result.get('success'):
            success_count += 1
            # Save to CSV
            with open(csv_file, 'a') as f:
                f.write(f"{i+1},{email},{time.strftime('%Y-%m-%d %H:%M:%S')},success\n")
        else:
            fail_count += 1
        
        print(f"[*] Progress: {success_count} success, {fail_count} failed")
        
        # Rate limit wait
        if result.get('rate_limited'):
            print("[*] Rate limited - waiting 3 minutes...")
            time.sleep(180)
        elif i < count - 1:
            time.sleep(30)  # 30 second gap between attempts
    
    xvfb.terminate()
    xvfb.wait()
    
    print(f"\n{'='*50}")
    print(f"[+] DONE: {success_count} added, {fail_count} failed out of {count}")

if __name__ == '__main__':
    main()
