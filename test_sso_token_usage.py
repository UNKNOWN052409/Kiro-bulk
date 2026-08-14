"""Test if the SSO session token can be used for AWS API calls."""
import sys, os, time, string, random, uuid, json
from playwright.sync_api import sync_playwright
import boto3
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

email = sys.argv[1] if len(sys.argv) > 1 else "testpy038@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

sso_token = None

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
    
    # Navigate to AWS SSO portal directly (not device flow)
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    # Check if already logged in (from previous sessions)
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"[+] Initial body (first 200 chars): {body[:200]}")
    
    # If not logged in, we need to go through the login flow
    # But for this test, let's use the device flow approach since we know it works
    
    page.close()
    context.close()

# Let's use the device flow approach but capture the SSO session token
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

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
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
    
    time.sleep(3)
    print(f"[+] Final URL: {page.url}")
    
    # Capture the SSO session token
    # After authorization, the SPA calls session/device which returns the token
    # Let's wait for the SPA to make this call, then capture it from network
    # Or we can call it directly
    
    # Get all cookies
    cookies = context.cookies()
    sso_cookie = None
    for c in cookies:
        if c['name'] == 'x-amz-sso_authn':
            sso_cookie = c['value']
            print(f"[+] x-amz-sso_authn cookie: {c['value'][:80]}...")
    
    # Call session/device to get the token
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://portal.sso.us-east-1.amazonaws.com/session/device', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include'
            });
            const data = await resp.json();
            return {status: resp.status, token: data.token || null, allKeys: Object.keys(data)};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"[+] session/device result: {json.dumps(result, indent=2)[:500]}")
    
    if result.get('token'):
        sso_token = result['token']
        print(f"[+] SSO Token captured: {sso_token[:50]}...")
    
    page.close()
    context.close()

# Now test if the SSO token can be used for AWS API calls
if sso_token:
    print("\n[*] Testing SSO token with AWS API...")
    
    # Try list_accounts with the SSO token
    headers = {'x-amz-sso_authn': sso_token}
    
    # Try the SSO portal API
    resp = requests.get('https://portal.sso.us-east-1.amazonaws.com/federation/credentials?account_id=&role_name=',
                       headers=headers, timeout=10)
    print(f"[+] SSO credentials API: {resp.status_code} {resp.text[:200]}")
    
    # Try the SSO list accounts
    resp2 = requests.get('https://portal.sso.us-east-1.amazonaws.com/instance/appinstances',
                        headers=headers, timeout=10)
    print(f"[+] SSO appinstances API: {resp2.status_code} {resp2.text[:200]}")
    
    # Save the token for later use
    with open('/tmp/sso_token_final.txt', 'w') as f:
        f.write(sso_token)
    print(f"[+] SSO token saved to /tmp/sso_token_final.txt")
