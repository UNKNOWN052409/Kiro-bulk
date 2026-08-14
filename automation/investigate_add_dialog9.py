import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

network_requests = []

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)

    # Capture network requests
    def on_request(request):
        if not request.url.startswith('data:'):
            network_requests.append(('REQ', request.method, request.url[:200]))
    
    page.on("request", on_request)

    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Login: {r}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)
    
    # Clear accumulated network requests
    network_requests.clear()

    # Click Add
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
    page.wait_for_timeout(8000)

    # Check network requests made after clicking
    print(f'\n=== NETWORK REQUESTS AFTER CLICK ({len(network_requests)}) ===')
    for t, m, url in network_requests[-30:]:
        print(f'  {m} {url}')

    # Check if the dialog has a form element  
    has_form = page.evaluate('''() => {
        const overlays = document.querySelectorAll('.fixed.inset-0');
        for (const o of overlays) {
            const body = o.querySelector('.p-6');
            if (body) return {
                innerHTML: body.innerHTML.substring(0, 2000),
                inputCount: body.querySelectorAll('input').length,
                buttonCount: body.querySelectorAll('button').length,
                text: body.innerText.substring(0, 500)
            };
        }
        return null;
    }''')
    print(f'\n=== DIALOG BODY ===')
    print(json.dumps(has_form, indent=2))

    # Try using Playwright's native click as fallback
    print('\n=== TRYING PLAYWRIGHT NATIVE CLICK ===')
    try:
        page.locator('button:has-text("AWS Builder ID")').first.click(timeout=5000)
        page.wait_for_timeout(5000)
        print('  Native click succeeded')
        
        # Recheck dialog
        body2 = page.evaluate('''() => {
            const overlays = document.querySelectorAll('.fixed.inset-0');
            for (const o of overlays) {
                const b = o.querySelector('.p-6');
                if (b) return b.innerHTML.substring(0, 2000);
            }
            return '';
        }''')
        print(f'  Dialog body after native click: {body2[:1000]}')
    except Exception as e:
        print(f'  Native click failed: {e}')

    input('\nPress Enter to close...')
