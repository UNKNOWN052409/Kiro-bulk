import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

popup_urls = []

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)

    # Listen for popups
    def on_popup(popup):
        popup_urls.append(popup.url)
        print(f'\n  [POPUP OPENED] {popup.url}')
    
    page.on("popup", on_popup)

    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Login: {r}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)

    print('=== CLICKING ADD ===')
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
    page.wait_for_timeout(8000)

    print(f'\n=== POPUP URLS: {popup_urls}')

    # Check all pages/contexts
    print(f'\n  Contexts: {len(browser.contexts)}')
    for ci, ctx in enumerate(browser.contexts):
        print(f'  Context {ci}: {len(ctx.pages)} pages')
        for pi, p in enumerate(ctx.pages):
            print(f'    Page {pi}: {p.url}')

    # Full page text analysis
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    lines = body.split('\n')
    # Find where "Connect Kiro" is
    for i, l in enumerate(lines):
        ls = l.strip()
        if ls and ('Connect Kiro' in ls or 'AWS Builder' in ls or 'Enter email' in ls or 'Sign in' in ls or 'credentials' in ls.lower() or 'email' == ls.lower().strip() or 'password' == ls.lower().strip()):
            # Print surrounding context
            start = max(0, i-2)
            end = min(len(lines), i+5)
            for j in range(start, end):
                print(f'  [{j}] {lines[j].strip()}')
            print('  ---')

    input('\nPress Enter to close...')
