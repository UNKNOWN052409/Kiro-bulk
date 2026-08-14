from playwright.sync_api import sync_playwright
import time, uuid, secrets, hashlib, base64, requests, random, string

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

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
name = "Rohan Patel"
password = "TestPass5678!"

print(f"Email: {email}")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        proxy={'server': 'socks5://127.0.0.1:10800', 'bypass': '<-loopback>,*.amazonaws.com,*.awsapps.com,*.signin.aws,*.amazon.com'},
        args=[
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--disable-blink-features=AutomationControlled',
        ],
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='America/New_York',
    )
    page = context.new_page()
    
    # Remove webdriver flag
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    
    # Navigate to auth URL
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    except:
        pass
    
    # Wait for sign-in page (loads fast without proxy)
    for i in range(15):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            if 'email' in body.lower() and 'continue' in body.lower():
                print("  Sign-in page loaded!")
                break
        except:
            pass
    
    # Enter email
    print(f"  Entering email: {email}")
    try:
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
        if email_inp:
            email_inp.fill(email)
            time.sleep(2)
            btn = page.get_by_role("button", name="Continue", exact=True).first
            btn.click()
            print("  Email submitted!")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Wait for Name page with LONG timeout
    print("  Waiting for Name page (up to 120s)...")
    name_page_loaded = False
    for i in range(60):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'enter your name' in body.lower():
                print(f"  Name page loaded at {i*2}s! URL: {url[:60]}")
                name_page_loaded = True
                break
            elif i % 10 == 0:
                print(f"  [{i*2}s] url={url[:60]} body_len={len(body)}")
        except:
            pass
    
    if not name_page_loaded:
        print("  [!] Name page never loaded through proxy")
        browser.close()
        exit()
    
    # Human-like delay before entering name
    time.sleep(random.uniform(3, 5))
    
    # Enter name
    print(f"  Entering name: {name}")
    try:
        name_inputs = page.locator('input[type="text"]').all()
        visible_name = [inp for inp in name_inputs if inp.is_visible()]
        if visible_name:
            visible_name[0].fill(name)
            time.sleep(2)
            btn = page.get_by_role("button", name="Continue", exact=True).first
            btn.click()
            print("  Name submitted!")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Wait for next page
    print("  Waiting for next page (OTP/Password)...")
    for i in range(20):
        time.sleep(3)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            print(f"  [{i*3}s] url={url[:60]} body={body[:80]}")
            if len(body) > 100 and 'enter your name' not in body.lower():
                break
        except:
            pass
    
    browser.close()
