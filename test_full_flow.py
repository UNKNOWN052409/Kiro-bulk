"""Full flow: device auth → browser → token (synchronous polling)."""
import sys, os, time, string, random, uuid
from playwright.sync_api import sync_playwright
from botocore.exceptions import ClientError
import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

# Get fresh device auth
print("[*] Registering OIDC client...")
client = boto3.client('sso-oidc', region_name='us-east-1')
reg = client.register_client(clientName=f'kiro-{uuid.uuid4().hex[:8]}', clientType='public')
device = client.start_device_authorization(
    clientId=reg['clientId'],
    clientSecret=reg['clientSecret'],
    startUrl='https://view.awsapps.com/start'
)
user_code = device['userCode']
device_code = device['deviceCode']
print(f"[+] User code: {user_code}")
print(f"[+] Device code: {device_code[:20]}...")

# Start token poll in background thread
import threading
token_received = [None]
poll_done = threading.Event()

def poll_token():
    poll_client = boto3.client('sso-oidc', region_name='us-east-1')
    deadline = time.time() + 540  # 9 min
    while time.time() < deadline:
        time.sleep(1)
        try:
            resp = poll_client.create_token(
                clientId=reg['clientId'],
                clientSecret=reg['clientSecret'],
                grantType='urn:ietf:params:oauth:grant-type:device_code',
                deviceCode=device_code
            )
            token = resp.get('refreshToken')
            if token:
                print(f"[+] TOKEN RECEIVED! len={len(token)}")
                token_received[0] = token
                poll_done.set()
                return
        except ClientError as e:
            err = e.response['Error']['Code']
            if err not in ('AuthorizationPendingException', 'SlowDownException'):
                print(f"[!] Poll error: {err}")
                poll_done.set()
                return
        except Exception as e:
            print(f"[!] Poll error: {e}")
            poll_done.set()
            return
    print("[!] Poll timed out")
    poll_done.set()

poll_thread = threading.Thread(target=poll_token, daemon=True)
poll_thread.start()
print("[+] Token poll started (thread)")

# Browser flow
email = sys.argv[1] if len(sys.argv) > 1 else "testpy029@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)
print(f"[*] Password: {password}")

def safe_eval(page, js, default=''):
    try:
        result = page.evaluate(js)
        return result if result is not None else default
    except Exception:
        return default

def wait_for_body(page, min_len=50, max_wait=30):
    for _ in range(max_wait):
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        if body and len(body) > min_len:
            return body
        time.sleep(1)
    return safe_eval(page, "document.body ? document.body.innerText : ''")

def dismiss_cookies(page):
    for _ in range(10):
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    try:
                        if btn.is_visible(timeout=1000):
                            btn.click(timeout=2000)
                            time.sleep(0.5)
                    except Exception:
                        pass
            except Exception:
                pass
        time.sleep(1)
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        if body and len(body) > 50 and 'cookie' not in body.lower()[:100]:
            break
    time.sleep(2)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Device page
    page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    # Click Continue
    for sel in ['button:has-text("Continue")', 'button:visible']:
        try:
            page.locator(sel).first.click(timeout=10000)
            print("[+] Device Continue clicked")
            break
        except Exception:
            continue
    time.sleep(8)
    
    # Dismiss cookies
    dismiss_cookies(page)
    
    # Email
    body = wait_for_body(page, min_len=50)
    print(f"[+] On email page")
    try:
        inp = page.locator('input:not([type="password"]):visible').first
        inp.wait_for(timeout=10000)
        inp.fill(email)
        time.sleep(0.5)
        inp.press('Enter')
        print(f"[+] Email submitted")
    except Exception as e:
        print(f"[!] Email error: {e}")
    time.sleep(5)
    dismiss_cookies(page)
    
    # Name
    body = wait_for_body(page, min_len=50)
    if 'name' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.fill(name)
            time.sleep(0.5)
            page.locator('button:has-text("Continue")').first.click(timeout=3000)
            print("[+] Name submitted")
        except Exception as e:
            print(f"[!] Name error: {e}")
        time.sleep(5)
    dismiss_cookies(page)
    
    # OTP
    body = wait_for_body(page, min_len=50)
    if 'verify' in body.lower() or 'code' in body.lower():
        otp = extract_otp_gmail_v3(email)
        if otp:
            try:
                inp = page.locator('input:visible').first
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP submitted: {otp}")
            except Exception as e:
                print(f"[!] OTP error: {e}")
            time.sleep(5)
    dismiss_cookies(page)
    
    # Password
    body = wait_for_body(page, min_len=50)
    if 'password' in body.lower():
        try:
            inputs = page.locator('input[type="password"]:visible').all()
            if inputs:
                inputs[0].fill(password)
                time.sleep(1)
                if len(inputs) > 1:
                    inputs[1].fill(password)
                time.sleep(1)
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=3000)
                    print("[+] Password submitted")
                except Exception:
                    inputs[-1].press('Enter')
                    print("[+] Password Enter")
        except Exception as e:
            print(f"[!] Password error: {e}")
        time.sleep(5)
    dismiss_cookies(page)
    
    # Allow - two step
    body = wait_for_body(page, min_len=50)
    buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    print(f"[+] Allow page - buttons: {buttons}")
    
    if 'Confirm and continue' in buttons:
        print("[*] Step 1: Confirm and continue...")
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        dismiss_cookies(page)
        
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        print(f"[+] After confirm - buttons: {buttons}")
        
        if 'Allow' in buttons or ('allow' in body.lower() and 'confirm this code' not in body.lower()):
            print("[*] Step 2: Clicking Allow...")
            try:
                page.locator('button:has-text("Allow")').first.click(timeout=5000)
                print("[+] Allow clicked!")
            except Exception:
                page.keyboard.press('Enter')
                print("[+] Enter pressed!")
    elif 'Allow' in buttons:
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    time.sleep(5)
    print(f"[+] Final URL: {page.url}")
    
    page.close()
    context.close()

# Wait for token
print("[*] Waiting for token...")
poll_done.wait(timeout=120)
if token_received[0]:
    print(f"[+] TOKEN: {token_received[0][:50]}...")
    with open('/tmp/kiro_token_captured.txt', 'w') as f:
        f.write(token_received[0])
    print("[+] Token saved!")
else:
    print("[!] Token NOT received")
