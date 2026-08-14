import sys, json, time, re
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

TEST_EMAIL = "michaelcarter@havenhaus.in"
TEST_PASSWORD = "Q6j%xpM$qYYSe6xa"

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    ctx = browser.new_context()
    page = ctx.new_page()
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
    
    # Wait for device code content to load (needs to fetch from server)
    device_url = None
    user_code = None
    for _ in range(15):
        page.wait_for_timeout(1000)
        device_info = page.evaluate('''() => {
            const overlays = document.querySelectorAll('.fixed.inset-0');
            for (const o of overlays) {
                const body = o.querySelector('.p-6');
                if (body) return body.innerText;
            }
            return '';
        }''')
        url_match = re.search(r'https://view\.awsapps\.com[^\s]*', device_info)
        if url_match:
            device_url = url_match.group(0)
            code_match = re.search(r'Your Code\s*\n\s*([A-Z0-9-]+)', device_info)
            if code_match:
                user_code = code_match.group(1)
            print(f'  Device URL found: {device_url}')
            print(f'  User Code: {user_code}')
            break
        print(f'  Waiting for device code... ({_+1}s)')
    
    if not device_url:
        print('  Could not get device URL')
        # Debug: print dialog content
        diag = page.evaluate('''() => {
            const o = document.querySelector('.fixed.inset-0');
            return o ? o.innerText.substring(0, 2000) : 'no dialog';
        }''')
        print(f'  Dialog: {diag}')
        sys.exit(1)

    # Open device URL in a new page
    print(f'\n=== OPENING DEVICE URL ===')
    auth_ctx = browser.new_context()
    auth_page = auth_ctx.new_page()
    auth_page.set_default_timeout(30000)

    try:
        auth_page.goto(device_url, wait_until='domcontentloaded', timeout=30000)
        auth_page.wait_for_timeout(5000)
        print(f'  Device page loaded: {auth_page.url}')
        
        # Sign in with AWS Builder ID
        body_text = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
        print(f'\n=== DEVICE PAGE TEXT ===')
        print(body_text[:2000])
        
        # Check for email input
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
            }}""")
            print(f'  Email filled: {TEST_EMAIL}')
            auth_page.wait_for_timeout(1000)
            
            # Click Continue
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
            auth_page.wait_for_timeout(8000)
            print(f'  URL after Continue: {auth_page.url}')
            
            # Check for password field
            has_pw = auth_page.evaluate("() => !!document.querySelector('input[type=\"password\"]')")
            print(f'  Has password: {has_pw}')
            
            if has_pw:
                # Fill password
                auth_page.evaluate(f"""() => {{
                    const el = document.querySelector('input[type="password"]');
                    if (!el) return;
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, {json.dumps(TEST_PASSWORD)});
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}""")
                print('  Password filled')
                auth_page.wait_for_timeout(1000)
                
                # Click Sign in
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
                auth_page.wait_for_timeout(10000)
                print(f'  URL after sign in: {auth_page.url}')
                
                # Check if we're on the authorize page
                body_after = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
                print(f'\n=== AFTER SIGN IN ===')
                print(body_after[:2000])
                
                # Check for "Allow" or "Authorize" button
                has_allow = auth_page.evaluate('''() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = b.textContent.trim().toLowerCase();
                        if ((t.includes('allow') || t.includes('authorize')) && b.offsetWidth > 0) {
                            b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                            b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                            b.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                            return t;
                        }
                    }
                    return '';
                }''')
                if has_allow:
                    print(f'  Clicked: {has_allow}')
                    auth_page.wait_for_timeout(5000)
                    print(f'  URL after authorize: {auth_page.url}')
                
                # Check if panel detected the auth
                page.bring_to_front()
                page.wait_for_timeout(5000)
                panel_text = page.evaluate("() => document.body ? document.body.innerText : ''")
                if 'authorized' in panel_text.lower() or 'success' in panel_text.lower():
                    print(f'\n  [+] Panel detected authorization!')
                else:
                    # Check dialog content
                    diag2 = page.evaluate('''() => {
                        const o = document.querySelector('.fixed.inset-0');
                        return o ? o.innerText.substring(0, 500) : 'no dialog';
                    }''')
                    print(f'\n  Panel dialog: {diag2}')
            else:
                print('  No password field found')
                body_after = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
                print(f'  Page content: {body_after[:1000]}')
    except Exception as e:
        print(f'  Error: {e}')
        import traceback
        traceback.print_exc()
    
    input('\nPress Enter to close browser...')
