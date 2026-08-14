from playwright.sync_api import sync_playwright
import time, uuid, secrets, hashlib, base64, requests, random

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

def generate_email():
    import string
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

# Register OIDC client
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9996/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']
client_secret = reg_resp.json()['clientSecret']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9996/oauth/callback'
auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'

email = generate_email()
name = "Rahul Sharma"
password = "TestPass1234!"

print(f"Email: {email}")
print(f"Auth URL created")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--disable-blink-features=AutomationControlled',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
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
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = {runtime: {}};
    """)
    
    # Navigate to auth URL
    print("  Navigating to OIDC authorize URL...")
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    except:
        pass
    
    # Wait for sign-in page
    print("  Waiting for sign-in page...")
    for i in range(15):
        time.sleep(2)
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        if 'email' in body.lower() and 'continue' in body.lower():
            print("  Sign-in page loaded!")
            break
    
    # Human-like: move mouse randomly
    print("  Moving mouse randomly...")
    for _ in range(5):
        x = random.randint(100, 1100)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.3, 0.8))
    
    # Enter email with typing effect
    print(f"  Entering email: {email}")
    email_input = page.locator('input[type="email"]').first
    email_input.click()
    time.sleep(1)
    for char in email:
        page.keyboard.type(char, delay=random.uniform(50, 150))
        time.sleep(random.uniform(0.02, 0.05))
    time.sleep(random.uniform(2, 4))
    
    # Click Continue button
    print("  Clicking Continue...")
    continue_btn = page.get_by_role("button", name="Continue", exact=True).first
    continue_btn.click()
    
    # Wait for Name page (profile.aws.amazon.com)
    print("  Waiting for Name page...")
    for i in range(30):
        time.sleep(3)
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        url = page.url
        if 'enter your name' in body.lower():
            print(f"  Name page loaded! URL: {url[:80]}")
            break
    
    # Human-like: move mouse
    for _ in range(3):
        x = random.randint(100, 1100)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.3, 0.8))
    
    # Enter name with typing effect
    print(f"  Entering name: {name}")
    name_input = page.locator('input[type="text"]').first
    name_input.click()
    time.sleep(1)
    for char in name:
        page.keyboard.type(char, delay=random.uniform(50, 150))
        time.sleep(random.uniform(0.02, 0.05))
    time.sleep(random.uniform(2, 4))
    
    # Click Continue
    print("  Clicking Continue...")
    continue_btn = page.get_by_role("button", name="Continue", exact=True).first
    continue_btn.click()
    
    # Wait for next page (should be OTP or password)
    print("  Waiting for next page...")
    for i in range(30):
        time.sleep(3)
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        url = page.url
        print(f"  [{i*3}s] url={url[:80]} body={body[:100]}")
        if len(body) > 100 and 'enter your name' not in body.lower():
            break
    
    browser.close()
