"""Try to get the OIDC token using the browser's SSO session after Allow click."""
import sys, os, time, string, random, uuid, json
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

email = sys.argv[1] if len(sys.argv) > 1 else "testpy041@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

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
    
    time.sleep(5)
    print(f"[+] Final URL: {page.url}")
    
    # Now try to get the OIDC token using the browser's session
    # The SPA stored the token after associate_token. Let's try to get it
    # by calling the SSO portal's token endpoint with the session cookies
    
    # Try 1: Call the OIDC token endpoint with session cookies
    print("\n[*] Attempting to get OIDC token from browser session...")
    
    # The browser is on view.awsapps.com. Let's try to fetch the token
    # from the SSO portal API using the browser's cookies
    result = page.evaluate(f"""async () => {{
        const results = {{}};
        
        // Try 1: SSO portal federation credentials
        try {{
            const resp = await fetch('https://portal.sso.us-east-1.amazonaws.com/federation/credentials', {{
                credentials: 'include'
            }});
            results.federation = {{status: resp.status, body: (await resp.text()).substring(0, 200)}};
        }} catch(e) {{ results.federation = {{error: e.message}}; }}
        
        // Try 2: SSO portal session token
        try {{
            const resp = await fetch('https://portal.sso.us-east-1.amazonaws.com/session/token', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',
                body: JSON.stringify({{}})
            }});
            results.sessionToken = {{status: resp.status, body: (await resp.text()).substring(0, 200)}};
        }} catch(e) {{ results.sessionToken = {{error: e.message}}; }}
        
        // Try 3: Check localStorage for tokens
        try {{
            const ls = {{}};
            for (let i = 0; i < localStorage.length; i++) {{
                const key = localStorage.key(i);
                const val = localStorage.getItem(key);
                ls[key] = typeof val === 'string' ? val.substring(0, 80) : val;
            }}
            results.localStorage = ls;
        }} catch(e) {{ results.localStorage = {{error: e.message}}; }}
        
        // Try 4: Check sessionStorage
        try {{
            const ss = {{}};
            for (let i = 0; i < sessionStorage.length; i++) {{
                const key = sessionStorage.key(i);
                const val = sessionStorage.getItem(key);
                ss[key] = typeof val === 'string' ? val.substring(0, 80) : val;
            }}
            results.sessionStorage = ss;
        }} catch(e) {{ results.sessionStorage = {{error: e.message}}; }}
        
        return results;
    }}""")
    print(f"[+] Browser session results: {json.dumps(result, indent=2)[:2000]}")
    
    page.close()
    context.close()
