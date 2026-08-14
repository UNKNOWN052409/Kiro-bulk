"""Test if the SSO session token can be used to get AWS credentials."""
import sys, os, time, string, random, uuid, json
from playwright.sync_api import sync_playwright
import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

# Get device auth
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

email = sys.argv[1] if len(sys.argv) > 1 else "testpy034@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

sso_session_token = None
sso_access_token = None

def on_response(response):
    global sso_session_token, sso_access_token
    url = response.url
    if '/session/device' in url:
        try:
            body = response.json()
            sso_session_token = body.get('token', '')
            print(f"[+] SSO session token captured: {sso_session_token[:50]}...")
        except Exception:
            pass
    if 'accessToken' in str(response.url) or '/credentials' in str(response.url):
        try:
            body = response.json()
            if 'accessToken' in body:
                sso_access_token = body['accessToken']
                print(f"[+] SSO access token captured!")
        except Exception:
            pass

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
    page.on("response", on_response)
    
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
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
    elif 'Allow' in buttons:
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    time.sleep(5)
    print(f"[+] Final URL: {page.url}")
    page.close()
    context.close()

# Now try to use the SSO session token
if sso_session_token:
    print(f"\n[*] SSO Session Token: {sso_session_token[:80]}...")
    
    # Try to use it with AWS SSO client
    sso_client = boto3.client('sso', region_name='us-east-1')
    
    # List accounts
    try:
        resp = sso_client.list_accounts(
            accessToken=sso_session_token
        )
        print(f"\n[+] Accounts found: {len(resp.get('accountList', []))}")
        for acc in resp.get('accountList', [])[:5]:
            print(f"    {acc.get('accountId')}: {acc.get('accountName')}")
    except Exception as e:
        print(f"[!] List accounts error: {e}")
    
    # Try list_account_roles
    try:
        # First get account list
        accounts = sso_client.list_accounts(accessToken=sso_session_token).get('accountList', [])
        if accounts:
            acc_id = accounts[0]['accountId']
            roles = sso_client.list_account_roles(
                accessToken=sso_session_token,
                accountId=acc_id
            )
            print(f"\n[+] Roles for {acc_id}: {len(roles.get('roleList', []))}")
            for role in roles.get('roleList', [])[:5]:
                print(f"    {role.get('roleName')}")
    except Exception as e:
        print(f"[!] List roles error: {e}")
else:
    print("\n[!] No SSO session token captured")

# Save the token if captured
if sso_session_token:
    with open('/tmp/sso_session_token.txt', 'w') as f:
        f.write(sso_session_token)
    print(f"\n[+] SSO session token saved to /tmp/sso_session_token.txt")
