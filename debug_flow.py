"""Debug the Kiro signup flow with screenshots at each step."""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9998
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

email = 'debugtest3@havenhaus.in'
full_name = 'Test User Debug'

# Register OIDC client
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
    context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US')
    page = context.new_page()
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(30000)
    
    step = 0
    
    def screenshot(name):
        global step
        step += 1
        try:
            page.screenshot(path=f'/home/ubuntu/kiro-gen/step{step:02d}_{name}.png', timeout=10000)
            print(f"  Screenshot: step{step:02d}_{name}.png")
        except Exception as e:
            print(f"  Screenshot error: {e}")
    
    # Navigate
    print("\n[1] Navigate to auth URL...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)
    print(f"  URL: {page.url[:100]}")
    try:
        page.screenshot(path=f'/home/ubuntu/kiro-gen/step00_auth_redirect.png', timeout=10000)
    except:
        pass
    
    # Wait for email form
    print("\n[2] Waiting for email form...")
    for i in range(15):
        time.sleep(1)
        body = page.evaluate('document.body.innerText')
        if 'email' in body.lower() and 'continue' in body.lower():
            print(f"  Form ready at {i}s: {body[:40]}")
            break
    
    # Check what inputs are available
    input_info = page.evaluate("""
        () => {
            const results = [];
            function collectInputs(root) {
                root.querySelectorAll('input').forEach(inp => {
                    results.push({
                        type: inp.type,
                        placeholder: inp.placeholder,
                        ariaLabel: inp.getAttribute('aria-label'),
                        name: inp.getAttribute('name'),
                        id: inp.id,
                    });
                });
                root.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) {
                        el.shadowRoot.querySelectorAll('input').forEach(inp => {
                            results.push({
                                type: inp.type,
                                placeholder: inp.placeholder,
                                ariaLabel: inp.getAttribute('aria-label'),
                                name: inp.getAttribute('name'),
                                id: inp.id,
                                inShadow: true,
                            });
                        });
                    }
                });
            }
            collectInputs(document);
            return JSON.stringify(results);
        }
    """)
    print(f"  All inputs: {input_info[:500]}")
    screenshot('email_form_inputs')
    
    # Fill email
    print("\n[3] Fill email and click Continue...")
    email_input = page.locator('input[type="email"]').first
    email_input.fill(email)
    time.sleep(1)
    screenshot('email_filled')
    
    continue_btn = page.locator('button:has-text("Continue")').first
    continue_btn.click()
    print("  Continue clicked")
    
    # Wait for name step - long wait
    print("\n[4] Waiting for name step (up to 20s)...")
    for i in range(20):
        time.sleep(1)
        try:
            url = page.url
            body = page.evaluate('document.body.innerText')
            
            if i < 10:
                print(f"  [{i}s] URL: {url[:80]}")
                print(f"  [{i}s] Body: {body[:60]}")
            
            # Check for name page
            if 'name' in body.lower() and ('enter' in body.lower()):
                # Check inputs on this page
                name_input_info = page.evaluate("""
                    () => {
                        const results = [];
                        function collectInputs(root) {
                            root.querySelectorAll('input').forEach(inp => {
                                results.push({
                                    type: inp.type,
                                    placeholder: inp.placeholder,
                                    ariaLabel: inp.getAttribute('aria-label'),
                                    name: inp.getAttribute('name'),
                                    value: inp.value,
                                });
                            });
                            root.querySelectorAll('*').forEach(el => {
                                if (el.shadowRoot) {
                                    el.shadowRoot.querySelectorAll('input').forEach(inp => {
                                        results.push({
                                            type: inp.type,
                                            placeholder: inp.placeholder,
                                            ariaLabel: inp.getAttribute('aria-label'),
                                            name: inp.getAttribute('name'),
                                            value: inp.value,
                                            inShadow: true,
                                        });
                                    });
                                }
                            });
                        }
                        collectInputs(document);
                        return JSON.stringify(results);
                    }
                """)
                print(f"  NAME PAGE inputs: {name_input_info[:500]}")
                screenshot(f'name_page_{i}')
                break
        except Exception as e:
            if i < 5:
                print(f"  [{i}s] Error: {str(e)[:80]}")
    
    # Wait more for the page to fully render
    print("\n[5] Waiting 10 more seconds for full render...")
    time.sleep(10)
    screenshot('name_page_after_wait')
    
    # Now check all inputs again
    all_inputs = page.evaluate("""
        () => {
            const results = [];
            function collectInputs(root) {
                root.querySelectorAll('input').forEach(inp => {
                    const style = window.getComputedStyle(inp);
                    results.push({
                        type: inp.type,
                        placeholder: inp.placeholder,
                        ariaLabel: inp.getAttribute('aria-label'),
                        name: inp.getAttribute('name'),
                        value: inp.value,
                        visible: style.display !== 'none' && style.visibility !== 'hidden',
                    });
                });
                root.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) {
                        el.shadowRoot.querySelectorAll('input').forEach(inp => {
                            results.push({
                                type: inp.type,
                                placeholder: inp.placeholder,
                                ariaLabel: inp.getAttribute('aria-label'),
                                name: inp.getAttribute('name'),
                                value: inp.value,
                                visible: true,
                                inShadow: true,
                            });
                        });
                    }
                });
            }
            collectInputs(document);
            return JSON.stringify(results);
        }
    """)
    print(f"  All inputs after wait: {all_inputs[:500]}")
    
    # Check buttons
    buttons = page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('button').forEach(btn => {
                results.push({text: btn.innerText.trim(), type: btn.type});
            });
            return JSON.stringify(results);
        }
    """)
    print(f"  Buttons: {buttons}")
    
    browser.close()
    
print("\nDone!")
