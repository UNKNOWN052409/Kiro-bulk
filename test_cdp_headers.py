"""Check associate_token response headers via CDP."""
import sys, os, time, string, random, uuid
from playwright.sync_api import sync_playwright
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
print(f"[+] User code: {user_code}")

email = sys.argv[1] if len(sys.argv) > 1 else "testpy036@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

assoc_response_info = {}

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    cdp = page.context.new_cdp_session(page)
    cdp.send('Network.enable')
    
    def on_response_received(params):
        resp = params.get('response', {})
        url = resp.get('url', '')
        if 'associate_token' in url:
            request_id = params.get('requestId')
            assoc_response_info['request_id'] = request_id
            assoc_response_info['headers'] = resp.get('headers', {})
            assoc_response_info['status'] = resp.get('status')
            assoc_response_info['mimeType'] = resp.get('mimeType')
            print(f"[+] associate_token response: status={resp.get('status')}, mimeType={resp.get('mimeType')}")
            print(f"[+] Headers: {json.dumps(resp.get('headers', {}), indent=2)}")
    
    def on_loading_finished(params):
        request_id = params.get('requestId')
        if request_id == assoc_response_info.get('request_id'):
            print(f"[+] Loading finished for associate_token")
            # Try to get body
            try:
                body_result = cdp.send('Network.getResponseBody', {'requestId': request_id})
                body = body_result.get('body', '')
                base64 = body_result.get('base64Encoded', False)
                assoc_response_info['body'] = body
                assoc_response_info['base64'] = base64
                print(f"[+] Body length: {len(body)}, base64: {base64}")
                if body:
                    if base64:
                        import base64
                        decoded = base64.b64decode(body).decode('utf-8', errors='replace')
                        print(f"[+] Decoded body: {decoded[:500]}")
                    else:
                        print(f"[+] Body: {body[:500]}")
            except Exception as e:
                print(f"[!] Error getting body: {e}")
    
    cdp.on('Network.responseReceived', on_response_received)
    cdp.on('Network.loadingFinished', on_loading_finished)
    
    # Device page
    page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    page.locator('button:has-text("Continue")').first.click(timeout=10000)
    time.sleep(8)
    
    for btn_text in ["Decline", "Dismiss", "Accept"]:
        try:
            btns = page.locator(f'button:has-text("{btn_text}")').all()
            for btn in btns:
                if btn.is_visible(timeout=1000):
                    btn.click(timeout=2000)
                    time.sleep(0.5)
        except Exception:
            pass
    time.sleep(2)
    
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
    
    # Allow
    body = page.evaluate("document.body ? document.body.innerText : ''")
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    
    if 'Confirm and continue' in buttons:
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        time.sleep(0.5)
            except Exception:
                pass
        time.sleep(2)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        if 'Allow' in buttons:
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
    elif 'Allow' in buttons:
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    time.sleep(5)
    page.close()
    context.close()

# Also try to get the token via create_token after everything
print("\n[*] Trying create_token after browser flow...")
import time as t
start = t.time()
while t.time() - start < 60:
    t.sleep(0.5)
    try:
        resp = client.create_token(
            clientId=reg['clientId'],
            clientSecret=reg['clientSecret'],
            grantType='urn:ietf:params:oauth:grant-type:device_code',
            deviceCode=device_code
        )
        token = resp.get('refreshToken')
        if token:
            print(f"[+] TOKEN CAPTURED! len={len(token)}")
            break
    except Exception as e:
        err = e.response['Error']['Code'] if hasattr(e, 'response') else str(e)
        if err not in ('AuthorizationPendingException', 'SlowDownException'):
            print(f"[!] create_token error: {err}")
            break
else:
    print("[!] create_token failed after 60s")

import json
print(f"\n[+] Response info: {json.dumps(assoc_response_info, indent=2)[:2000]}")
