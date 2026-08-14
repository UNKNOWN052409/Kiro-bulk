"""Navigate to the name page on profile.aws.amazon.com and fill the name."""

import uuid, secrets, hashlib, base64, requests, json, time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions"]
CALLBACK_PORT = 9998
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

email = 'debugname5@havenhaus.in'
full_name = 'Maria Jose Silva'

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
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote("codewhisperer:completions")}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
    context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US')
    page = context.new_page()
    page.set_default_timeout(60000)
    page.set_default_navigation_timeout(60000)
    
    # Navigate
    print("[1] Navigate...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)
    
    # Wait for email form
    print("[2] Email form...")
    for i in range(20):
        time.sleep(1)
        try:
            body = page.evaluate('document.body.innerText')
            if 'email' in body.lower() and 'continue' in body.lower():
                print(f"  Ready at {i}s")
                break
        except:
            pass
    
    # Fill email
    print("[3] Fill email...")
    email_input = page.locator('input[type="email"]').first
    email_input.fill(email)
    time.sleep(0.5)
    continue_btn = page.locator('button:has-text("Continue")').first
    continue_btn.click()
    print("  Submitted")
    
    # Wait for name page on profile.aws.amazon.com
    print("[4] Waiting for name page...")
    for i in range(30):
        time.sleep(1)
        try:
            url = page.url
            body = page.evaluate('document.body.innerText')
            if 'profile.aws.amazon.com' in url and 'enter your name' in body.lower():
                print(f"  Name page at {i}s!")
                print(f"  URL: {url[:80]}")
                break
        except:
            pass
    
    # Wait extra for SPA to fully render
    time.sleep(5)
    
    # NOW find ALL elements that could be the name input
    print("\n[5] Finding name input...")
    element_info = page.evaluate("""
        () => {
            const results = [];
            function collectElements(root, isShadow) {
                // Find all focusable/editable elements
                root.querySelectorAll('input, [contenteditable], [role="textbox"], textarea').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    results.push({
                        tag: el.tagName,
                        type: el.type || el.getAttribute('type') || '',
                        placeholder: el.placeholder || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        name: el.getAttribute('name') || '',
                        id: el.id || '',
                        role: el.getAttribute('role') || '',
                        editable: el.isContentEditable,
                        visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0,
                        inShadow: isShadow,
                        rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)}
                    });
                });
                // Check shadow DOMs
                root.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) {
                        collectElements(el.shadowRoot, true);
                    }
                });
            }
            collectElements(document, false);
            return JSON.stringify(results);
        }
    """)
    print(f"  Editable elements: {element_info[:1000]}")
    
    # Try filling using Playwright locator (it should find elements in shadow DOM)
    print("\n[6] Trying Playwright locators...")
    
    # Try various locators
    try:
        # Standard input
        name_input = page.locator('input[placeholder]').first
        info = name_input.get_attribute('placeholder')
        print(f"  Found input with placeholder: {info}")
    except:
        pass
    
    # Try to find the name input specifically
    try:
        # The input might be inside a form or div with specific class
        name_input = page.locator('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"])').first
        placeholder = name_input.get_attribute('placeholder')
        print(f"  Found non-checkbox input, placeholder: {placeholder}")
    except Exception as e:
        print(f"  Locator error: {e}")
    
    # Try JS to find and interact with the name input
    print("\n[7] JS-based fill...")
    fill_result = page.evaluate(f"""
        () => {{
            const results = [];
            function collectEditable(root) {{
                root.querySelectorAll('input, [contenteditable], [role="textbox"], textarea').forEach(el => {{
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const visible = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                    if (visible) results.push(el);
                }});
                root.querySelectorAll('*').forEach(el => {{
                    if (el.shadowRoot) collectEditable(el.shadowRoot);
                }});
            }}
            collectEditable(document);
            
            // Find the name input (not checkbox, radio, etc.)
            let target = null;
            for (const el of results) {{
                const type = el.type || '';
                if (type !== 'checkbox' && type !== 'radio' && type !== 'hidden' && type !== 'submit') {{
                    target = el;
                    break;
                }}
            }}
            
            if (target) {{
                const name = '{full_name}';
                // Use native input value setter
                if (target instanceof HTMLInputElement) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(target, name);
                    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }} else if (target.isContentEditable) {{
                    target.textContent = name;
                    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
                target.focus();
                return 'FILLED: ' + name + ' (tag=' + target.tagName + ', type=' + (target.type||'') + ', placeholder=' + (target.placeholder||'') + ')';
            }}
            return 'NO_TARGET. Found ' + results.length + ' editable elements';
        }}
    """)
    print(f"  Result: {fill_result}")
    
    time.sleep(2)
    
    # Click Continue
    print("\n[8] Click Continue...")
    try:
        continue_btn2 = page.locator('button:has-text("Continue")').first
        is_visible = continue_btn2.is_visible()
        print(f"  Continue visible: {is_visible}")
        if is_visible:
            continue_btn2.click()
            print("  Continue clicked!")
            time.sleep(5)
            body = page.evaluate('document.body.innerText')
            print(f"  After Continue: {body[:100]}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Take screenshot
    try:
        page.screenshot(path='/home/ubuntu/kiro-gen/final_name.png', timeout=10000)
    except:
        pass
    
    # Wait and check next step
    print("\n[9] Checking next step...")
    for i in range(15):
        time.sleep(1)
        try:
            body = page.evaluate('document.body.innerText')
            url = page.url
            if 'otp' in body.lower() or 'code' in body.lower() or 'verification' in body.lower():
                print(f"  OTP step at {i}s: {body[:60]}")
                break
            elif i % 3 == 0:
                print(f"  [{i}s] URL: {url[:60]}, Body: {body[:40]}")
        except:
            pass
    
    browser.close()

print("\nDone!")
