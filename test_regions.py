#!/usr/bin/env python3
"""
Test different ProxyRise countries to find one that AWS doesn't flag.
We'll test the full flow with different countries.
"""

from cloakbrowser import launch
import time, uuid, secrets, hashlib, base64, requests, random, string, sys

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

COUNTRIES_TO_TEST = ['US', 'UK', 'CA', 'DE', 'NL', 'FR', 'AU', 'JP']

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

def register_oidc_client():
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": ["http://127.0.0.1:9998/oauth/callback"],
        "issuerUrl": ISSUER_URL
    }
    reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
    return reg_resp.json()

def create_pkce():
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return code_verifier, code_challenge

def test_country(country):
    """Test a specific country"""
    print(f"\n{'='*60}")
    print(f"Testing country: {country}")
    print(f"{'='*60}")
    
    # Register client
    client_info = register_oidc_client()
    client_id = client_info['clientId']
    
    # PKCE
    code_verifier, code_challenge = create_pkce()
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    redirect_uri = 'http://127.0.0.1:9998/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={redirect_uri}&scopes={scopes_encoded}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    email = generate_email()
    name = "Test User"
    
    print(f"Email: {email}")
    
    # Launch with country-specific proxy
    proxy_url = f"socks5://api-{country}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    
    try:
        browser = launch(
            proxy=proxy_url,
            geoip=True,
            headless=False,
            humanize=True,
        )
    except Exception as e:
        print(f"  Failed to launch browser: {e}")
        return False
    
    page = browser.new_page()
    
    # Check IP
    try:
        page.goto("https://ipinfo.io/json", wait_until='domcontentloaded', timeout=15000)
        time.sleep(2)
        ip_body = page.evaluate("() => document.body.innerText")
        print(f"  Proxy IP: {ip_body[:100]}")
    except:
        pass
    
    # Navigate to auth URL
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    except Exception as e:
        print(f"  Navigation error: {e}")
        browser.close()
        return False
    
    # Wait for sign-in page
    for i in range(10):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            if 'email' in body.lower() and 'continue' in body.lower():
                break
        except:
            pass
    
    # Enter email
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
        email_inp.fill(email)
        time.sleep(1)
        btn = page.get_by_role("button", name="Continue", exact=True).first
        btn.click()
    except Exception as e:
        print(f"  Email error: {e}")
        browser.close()
        return False
    
    # Wait for Name page
    name_loaded = False
    for i in range(30):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'enter your name' in body.lower():
                name_loaded = True
                print(f"  Name page loaded at {i*2}s!")
                break
            elif i % 5 == 0 and i > 0:
                print(f"  [{i*2}s] url={url[:60]} body_len={len(body)}")
        except:
            pass
    
    if not name_loaded:
        print(f"  Name page never loaded")
        browser.close()
        return False
    
    # Enter name
    try:
        name_inputs = page.locator('input[type="text"]').all()
        visible_name = [inp for inp in name_inputs if inp.is_visible()]
        if visible_name:
            visible_name[0].fill(name)
            time.sleep(1)
            btn = page.get_by_role("button", name="Continue", exact=True).first
            btn.click()
    except Exception as e:
        print(f"  Name error: {e}")
        browser.close()
        return False
    
    # Check for ERR-837
    for i in range(10):
        time.sleep(3)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'ERR-837' in body:
                print(f"  RESULT: ERR-837 (blocked)")
                browser.close()
                return False
            elif len(body) > 100 and 'enter your name' not in body.lower():
                print(f"  RESULT: SUCCESS (no ERR-837)!")
                print(f"  Body: {body[:200]}")
                browser.close()
                return True
            elif i == 5:
                print(f"  [{i*3}s] url={url[:60]} body_len={len(body)}")
        except:
            pass
    
    print(f"  RESULT: TIMEOUT (unclear)")
    browser.close()
    return False


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else COUNTRIES_TO_TEST[:2]
    
    results = {}
    for country in countries:
        result = test_country(country)
        results[country] = result
        print(f"\n  Country {country}: {'PASS' if result else 'FAIL'}")
    
    print(f"\n{'='*60}")
    print("SUMMARY:")
    for country, result in results.items():
        print(f"  {country}: {'PASS ✓' if result else 'FAIL ✗'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
