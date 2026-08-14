"""Block the SPA's associate_token call and use create_token ourselves."""
import sys, os, time, string, random, uuid, threading
from playwright.sync_api import sync_playwright
from botocore.exceptions import ClientError
import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

client = boto3.client('sso-oidc', region_name='us-east-1')
reg = client.register_client(clientName=f'kiro-{uuid.uuid4().hex[:8]}', clientType='public')
device = client.start_device_authorization(
    clientId=reg['clientId'],
    clientSecret=reg['clientSecret'],
    startUrl='https://view.awsapps.com/start'
)
user_code = device['userCode']
device_code = device['deviceCode']
expires_in = device.get('expiresIn', 600)
print(f"[+] User code: {user_code}")

email = sys.argv[1] if len(sys.argv) > 1 else "testpy035@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

captured_token = None
poll_done = threading.Event()

def poll_for_token():
    global captured_token
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(0.1)
        try:
            resp = client.create_token(
                clientId=reg['clientId'],
                clientSecret=reg['clientSecret'],
                grantType='urn:ietf:params:oauth:grant-type:device_code',
                deviceCode=device_code
            )
            token = resp.get('refreshToken')
            if token:
                captured_token = token
                with open('/tmp/kiro_token_captured.txt', 'w') as f:
                    f.write(token)
                print(f"\n[+] *** TOKEN CAPTURED! len={len(token)} ***")
                poll_done.set()
                return
        except ClientError as e:
            err = e.response['Error']['Code']
            if err not in ('AuthorizationPendingException', 'SlowDownException'):
                print(f"\n[!] Poll error: {err} - {e.response['Error'].get('Message','')}")
                poll_done.set()
                return
        except Exception as e:
            print(f"\n[!] Exception: {e}")
            poll_done.set()
            return

def dismiss_cookies_sync(page):
    for _ in range(10):
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        time.sleep(0.5)
            except Exception:
                pass
        time.sleep(1)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        if body and len(body) > 50 and 'cookie' not in body.lower()[:100]:
            break
    time.sleep(2)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Set up CDP to block associate_token requests
    cdp = page.context.new_cdp_session(page)
    cdp.send('Network.enable')
    
    def block_request(params):
        request_id = params.get('requestId')
        url = params.get('request', {}).get('url', '')
        if 'associate_token' in url:
            print(f"[+] BLOCKING associate_token request!")
            cdp.send('Fetch.failRequest', {'requestId': request_id, 'errorReason': 'BlockedByClient'})
    
    # Use Fetch domain to intercept and block
    cdp.send('Fetch.enable', {'patterns': [{'urlPattern': '*associate_token*', 'requestStage': 'Request'}]})
    cdp.on('Fetch.requestPaused', block_request)
    
    # Device page
    page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    page.locator('button:has-text("Continue")').first.click(timeout=10000)
    print("[+] Device Continue clicked")
    time.sleep(8)
    dismiss_cookies_sync(page)
    
    # Email
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'email' in body.lower() or 'sign in' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.wait_for(timeout=10000)
            inp.fill(email)
            inp.press('Enter')
            print("[+] Email submitted")
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Name
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'name' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.fill(name)
            page.locator('button:has-text("Continue")').first.click(timeout=3000)
            print("[+] Name submitted")
        except Exception as e:
            print(f"[!] Name: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # OTP
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'verify' in body.lower() or 'one-time' in body.lower() or ('code' in body.lower() and 'enter' in body.lower()):
        otp = extract_otp_gmail_v3(email)
        if otp:
            try:
                inp = page.locator('input:visible').first
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP: {otp}")
            except Exception as e:
                print(f"[!] OTP: {e}")
            time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Password
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'password' in body.lower():
        try:
            inputs = page.locator('input[type="password"]:visible').all()
            if inputs:
                inputs[0].fill(password)
                if len(inputs) > 1:
                    inputs[1].fill(password)
                page.locator('button:has-text("Continue")').first.click(timeout=3000)
                print("[+] Password submitted")
        except Exception as e:
            print(f"[!] Password: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Allow
    body = page.evaluate("document.body ? document.body.innerText : ''")
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    print(f"[+] Buttons: {buttons}")
    
    if 'Confirm and continue' in buttons:
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        dismiss_cookies_sync(page)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        if 'Allow' in buttons:
            # Start poll thread
            poll_thread = threading.Thread(target=poll_for_token, daemon=True)
            poll_thread.start()
            time.sleep(0.1)
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
    elif 'Allow' in buttons:
        poll_thread = threading.Thread(target=poll_for_token, daemon=True)
        poll_thread.start()
        time.sleep(0.1)
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    time.sleep(10)
    print(f"[+] Final URL: {page.url}")
    page.close()
    context.close()

poll_done.wait(timeout=60)
if captured_token:
    print(f"\n[+] SUCCESS! Token: {captured_token[:50]}...")
else:
    print("\n[!] Token not captured")
