"""Capture the token from browser network requests instead of polling."""
import sys, os, time, string, random, uuid, json
from playwright.sync_api import sync_playwright
import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

# Get fresh device auth
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

email = sys.argv[1] if len(sys.argv) > 1 else "testpy031@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

captured_tokens = []
captured_requests = []

def on_response(response):
    url = response.url
    if 'token' in url.lower() or 'oidc' in url.lower() or 'sso' in url.lower():
        captured_requests.append(url)
        try:
            body = response.json()
            captured_tokens.append(body)
            print(f"[+] Captured response from {url}")
            print(f"    Keys: {list(body.keys()) if isinstance(body, dict) else type(body)}")
            if isinstance(body, dict) and ('accessToken' in body or 'refreshToken' in body):
                print(f"    *** TOKEN FOUND! ***")
        except Exception:
            pass

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.on("response", on_response)
    
    # Device page
    page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    # Click Continue
    page.locator('button:has-text("Continue")').first.click(timeout=10000)
    print("[+] Device Continue clicked")
    time.sleep(8)
    
    # Check what page we're on
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"[+] Body: {body[:200]}")
    
    # Try to fill email if on email page
    if 'email' in body.lower() or 'sign in' in body.lower():
        # Dismiss cookie dialog
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        time.sleep(0.5)
            except:
                pass
        time.sleep(2)
        
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.wait_for(timeout=10000)
            inp.fill(email)
            inp.press('Enter')
            print("[+] Email submitted")
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(5)
    
    # Check for name page
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
    
    # Check for OTP page
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'verify' in body.lower() or 'code' in body.lower() or 'one-time' in body.lower():
        otp = extract_otp_gmail_v3(email)
        if otp:
            try:
                inp = page.locator('input:visible').first
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP submitted: {otp}")
            except Exception as e:
                print(f"[!] OTP: {e}")
            time.sleep(5)
    
    # Check for password page
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
    
    # Allow page
    body = page.evaluate("document.body ? document.body.innerText : ''")
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    print(f"[+] Buttons: {buttons}")
    
    if 'Confirm and continue' in buttons:
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        # Dismiss cookie dialog
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        time.sleep(0.5)
            except:
                pass
        time.sleep(2)
        
        body = page.evaluate("document.body ? document.body.innerText : ''")
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        print(f"[+] After confirm: {buttons}")
        
        if 'Allow' in buttons:
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
    elif 'Allow' in buttons:
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    time.sleep(5)
    print(f"[+] Final URL: {page.url}")
    page.close()
    context.close()

# Print captured requests and tokens
print(f"\n[*] Captured {len(captured_requests)} requests, {len(captured_tokens)} responses")
for i, req in enumerate(captured_requests):
    print(f"  [{i}] {req}")

if captured_tokens:
    for i, tok in enumerate(captured_tokens):
        print(f"  [{i}] {json.dumps(tok, indent=2)[:500]}")
