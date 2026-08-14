import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

# Use a REAL existing account from kiro_accounts.csv
TEST_EMAIL = "michaelcarter@havenhaus.in"
TEST_PASSWORD = "Q6j%xpM$qYYSe6xa"

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)

    # Login to panel
    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Panel login: {r}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)

    # Click Add
    print('\n=== CLICKING ADD ===')
    page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim().replace(/[\\s\\u00A0]/g, '');
            if (t === 'addAdd' && b.offsetWidth > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return;
            }
        }
    }''')
    page.wait_for_timeout(2000)

    # Click AWS Builder ID
    print('=== CLICKING AWS BUILDER ID ===')
    page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim();
            if (t.includes("AWS Builder ID") && b.offsetWidth > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return;
            }
        }
    }''')
    page.wait_for_timeout(5000)

    # Extract device URL and code
    device_info = page.evaluate('''() => {
        const overlays = document.querySelectorAll('.fixed.inset-0');
        for (const o of overlays) {
            const body = o.querySelector('.p-6');
            if (body) return {text: body.innerText, html: body.innerHTML};
        }
        return null;
    }''')
    
    if device_info:
        print(f'\n=== DEVICE FLOW CONTENT ===')
        print(device_info['text'][:1000])
        
        # Extract URL and code
        import re
        text = device_info['text']
        url_match = re.search(r'https://view\.awsapps\.com[^\s]*', text)
        code_match = re.search(r'Your Code\s*\n\s*([A-Z0-9-]+)', text)
        
        device_url = url_match.group(0) if url_match else None
        user_code = code_match.group(1) if code_match else None
        print(f'\n  Device URL: {device_url}')
        print(f'  User Code: {user_code}')
    else:
        print('No dialog content found')
        sys.exit(1)

    # Now open the device URL in a NEW page
    print(f'\n=== OPENING DEVICE URL IN NEW PAGE ===')
    auth_page = browser.contexts[0].new_page()
    auth_page.set_default_timeout(30000)

    try:
        auth_page.goto(device_url, wait_until='domcontentloaded', timeout=30000)
        print(f'  Device page loaded: {auth_page.url}')
        auth_page.wait_for_timeout(5000)
        
        # Check what the device page looks like
        body_text = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
        print(f'\n=== DEVICE PAGE TEXT ===')
        print(body_text[:1500])
        
        # Check if there's an email input
        has_email = auth_page.evaluate("() => !!document.querySelector('input[type=\"email\"]')")
        print(f'\n  Has email input: {has_email}')
        
        if has_email:
            # Fill email
            auth_page.evaluate(f"""() => {{
                const el = document.querySelector('input[type="email"]');
                if (!el) return;
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, {json.dumps(TEST_EMAIL)});
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                el.dispatchEvent(new Event('blur', {{bubbles: true}}));
            }}""")
            print(f'  Email filled: {TEST_EMAIL}')
            
            # Click Continue
            auth_page.wait_for_timeout(2000)
            auth_page.evaluate('''() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent.trim().includes("Continue") && b.offsetWidth > 0) {
                        b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                        b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                        b.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                        return;
                    }
                }
            }''')
            print('  Continue clicked')
            auth_page.wait_for_timeout(5000)
            print(f'  URL after Continue: {auth_page.url}')
            
            # Check for password field
            body2 = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
            print(f'\n=== AFTER CONTINUE ===')
            print(body2[:1000])
            
            has_pw = auth_page.evaluate("() => !!document.querySelector('input[type=\"password\"]')")
            print(f'\n  Has password input: {has_pw}')
            
            if has_pw:
                auth_page.evaluate(f"""() => {{
                    const el = document.querySelector('input[type="password"]');
                    if (!el) return;
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, {json.dumps(TEST_PASSWORD)});
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}""")
                print('  Password filled')
                auth_page.wait_for_timeout(2000)
                auth_page.evaluate('''() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.textContent.trim().includes("Sign in") && b.offsetWidth > 0) {
                            b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                            b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                            b.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                            return;
                        }
                    }
                }''')
                print('  Sign in clicked')
                auth_page.wait_for_timeout(8000)
                print(f'  URL after sign in: {auth_page.url}')
                body3 = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
                print(f'\n=== AFTER SIGN IN ===')
                print(body3[:1000])
    except Exception as e:
        print(f'  Error during auth: {e}')
    
    input('\nPress Enter to close browser...')
