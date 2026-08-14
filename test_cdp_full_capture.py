"""Full CDP capture of associate_token response."""
import sys, os, time, string, random, uuid, json, base64
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

email = sys.argv[1] if len(sys.argv) > 1 else "testpy039@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

captured_responses = {}

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
    
    cdp = page.context.new_cdp_session(page)
    cdp.send('Network.enable')
    
    def on_response(params):
        resp = params.get('response', {})
        url = resp.get('url', '')
        request_id = params.get('requestId')
        if 'associate_token' in url or 'session/device' in url:
            captured_responses[request_id] = {
                'url': url,
                'status': resp.get('status'),
                'headers': resp.get('headers', {}),
                'captured_body': False
            }
            print(f"[+] Response: {url[:80]} status={resp.get('status')}")
    
    def on_loading_finished(params):
        request_id = params.get('requestId')
        if request_id in captured_responses:
            try:
                body_result = cdp.send('Network.getResponseBody', {'requestId': request_id})
                body = body_result.get('body', '')
                is_base64 = body_result.get('base64Encoded', False)
                captured_responses[request_id]['captured_body'] = True
                captured_responses[request_id]['body_length'] = len(body)
                captured_responses[request_id]['base64'] = is_base64
                if body:
                    if is_base64:
                        decoded = base64.b64decode(body).decode('utf-8', errors='replace')
                        captured_responses[request_id]['body_text'] = decoded[:500]
                    else:
                        captured_responses[request_id]['body_text'] = body[:500]
                    print(f"[+] Body captured ({len(body)} bytes): {captured_responses[request_id]['body_text'][:200]}")
                else:
                    print(f"[+] Body: EMPTY ({len(body)} bytes)")
            except Exception as e:
                captured_responses[request_id]['body_error'] = str(e)
                print(f"[!] Body capture error: {e}")
    
    cdp.on('Network.responseReceived', on_response)
    cdp.on('Network.loadingFinished', on_loading_finished)
    
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
    
    if 'Confirm and continue' in buttons:
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        dismiss_cookies_sync(page)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        if 'Allow' in buttons:
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
    elif 'Allow' in buttons:
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    # Wait for responses to be captured
    time.sleep(5)
    print(f"[+] Final URL: {page.url}")
    page.close()
    context.close()

print(f"\n[+] Captured {len(captured_responses)} responses")
for rid, info in captured_responses.items():
    print(f"\n  Request: {rid}")
    print(f"  URL: {info['url'][:100]}")
    print(f"  Status: {info.get('status')}")
    print(f"  Body captured: {info.get('captured_body')}")
    print(f"  Body length: {info.get('body_length', 0)}")
    if 'body_text' in info:
        print(f"  Body text: {info['body_text'][:200]}")
    if 'body_error' in info:
        print(f"  Body error: {info['body_error']}")
