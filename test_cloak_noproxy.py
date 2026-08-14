from cloakbrowser import launch
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
    "redirectUris": ["http://127.0.0.1:9992/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9992/oauth/callback'
auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'

email = generate_email()
name = "Rajesh Kumar"

print(f"Email: {email}")
print("Launching CloakBrowser WITHOUT proxy...")

# NO proxy - let CloakBrowser's stealth patches handle it
browser = launch(headless=False, humanize=True)
page = browser.new_page()

# Navigate
page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)

# Wait for sign-in page
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
print("  Email submitted!")

# Wait for Name page
print("  Waiting for Name page...")
for i in range(30):
    time.sleep(3)
    try:
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        url = page.url
        if 'enter your name' in body.lower():
            print(f"  Name page loaded at {i*3}s! URL: {url[:60]}")
            break
        elif i % 5 == 0:
            print(f"  [{i*3}s] url={url[:60]} body_len={len(body)}")
    except:
        pass

# Enter name
print(f"  Entering name: {name}")
name_inputs = page.locator('input[type="text"]').all()
visible_name = [inp for inp in name_inputs if inp.is_visible()]
if visible_name:
    visible_name[0].fill(name)
    time.sleep(2)
    btn = page.get_by_role("button", name="Continue", exact=True).first
    btn.click()
    print("  Name submitted!")

# Wait for next page
print("  Waiting for next page...")
for i in range(15):
    time.sleep(3)
    try:
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        url = page.url
        print(f"  [{i*3}s] url={url[:60]} body={body[:100]}")
        if len(body) > 100 and 'enter your name' not in body.lower() and 'ERR-837' not in body:
            print("  SUCCESS - No ERR-837!")
            break
    except:
        pass

browser.close()
