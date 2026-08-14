#!/usr/bin/env python3
"""
CloakBrowser + ProxyRise (ALL traffic through proxy)
The key insight: CloakBrowser strips proxy detection signals.
We need to use proxy for ALL traffic including profile.aws.amazon.com.
The SPA should render because CloakBrowser removes timing signals.
"""

from cloakbrowser import launch
import time, uuid, secrets, hashlib, base64, requests, random, string

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

def generate_name():
    first_names = ["Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Reyansh", "Krishna", "Ishaan", "Shaurya", "Atharv",
                   "Aadhya", "Saanvi", "Ananya", "Diya", "Kiara", "Ira", "Myra", "Sara", "Aanya", "Anvi",
                   "Liam", "Noah", "Ethan", "Mason", "Lucas", "Oliver", "Elijah", "James", "William", "Benjamin"]
    last_names = ["Sharma", "Verma", "Singh", "Patel", "Kumar", "Gupta", "Mehta", "Joshi", "Reddy", "Nair",
                  "Rao", "Pillai", "Menon", "Iyer", "Bhat", "Desai", "Shah", "Chopra", "Malhotra", "Khanna"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

# Register OIDC client
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9995/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9995/oauth/callback'
auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'

email = generate_email()
name = generate_name()

print(f"Email: {email}")
print(f"Name: {name}")

# Launch CloakBrowser WITH proxy (all traffic)
# The key: geoip=True auto-configures timezone/locale from proxy IP
# humanize=True adds human-like behavior
proxy_url = f"socks5://api-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
print(f"\nLaunching CloakBrowser with proxy: {proxy_url}")

browser = launch(
    proxy=proxy_url,
    geoip=True,
    headless=False,
    humanize=True,
)

page = browser.new_page()

# Verify proxy is being used
page.goto("https://ipinfo.io/json", wait_until='domcontentloaded', timeout=15000)
time.sleep(2)
ip_body = page.evaluate("() => document.body.innerText")
print(f"\nProxy IP: {ip_body[:100]}")

# Navigate to auth URL
print(f"\nNavigating to authorize URL...")
try:
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
except Exception as e:
    print(f"Navigation error: {e}")

# Wait for sign-in page
print("Waiting for sign-in page...")
for i in range(15):
    time.sleep(2)
    try:
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        if 'email' in body.lower() and 'continue' in body.lower():
            print(f"  Sign-in page loaded at {i*2}s!")
            break
    except:
        pass

# Enter email
print(f"Entering email: {email}")
inputs = page.locator('input').all()
visible = [inp for inp in inputs if inp.is_visible()]
email_inp = None
for inp in visible:
    inp_type = inp.get_attribute('type') or 'text'
    if inp_type in ('email', 'text'):
        email_inp = inp
        break
if email_inp is None and visible:
    email_inp = visible[0]

email_inp.fill(email)
time.sleep(2)
btn = page.get_by_role("button", name="Continue", exact=True).first
btn.click()
print("Email submitted!")

# Wait for Name page (profile.aws.amazon.com)
print("Waiting for Name page (up to 120s)...")
name_loaded = False
for i in range(60):
    time.sleep(2)
    try:
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
        url = page.url
        if 'enter your name' in body.lower():
            print(f"  Name page loaded at {i*2}s! URL: {url[:60]}")
            name_loaded = True
            break
        elif i % 10 == 0:
            print(f"  [{i*2}s] url={url[:60]} body_len={len(body)} html_len={html_len}")
    except:
        pass

if name_loaded:
    # Enter name
    print(f"Entering name: {name}")
    time.sleep(random.uniform(2, 4))
    
    # Human-like mouse movement
    for _ in range(2):
        x = random.randint(100, 1100)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.2, 0.5))
    
    name_inputs = page.locator('input[type="text"]').all()
    visible_name = [inp for inp in name_inputs if inp.is_visible()]
    if visible_name:
        visible_name[0].fill(name)
        time.sleep(random.uniform(1.5, 3.0))
        btn = page.get_by_role("button", name="Continue", exact=True).first
        btn.click()
        print("Name submitted!")
    
    # Wait for next page - check for ERR-837 or progress
    print("Waiting for next page...")
    for i in range(20):
        time.sleep(3)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'ERR-837' in body:
                print(f"  [{i*3}s] ERR-837 detected!")
            elif len(body) > 100 and 'enter your name' not in body.lower():
                print(f"  [{i*3}s] SUCCESS! URL: {url[:60]}")
                print(f"  Body: {body[:200]}")
                break
            elif i % 3 == 0:
                print(f"  [{i*3}s] url={url[:60]} body_len={len(body)}")
        except:
            pass

browser.close()
print("\nDone!")
