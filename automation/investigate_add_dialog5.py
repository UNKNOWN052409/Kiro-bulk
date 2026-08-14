import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)

    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Login: {r}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)

    print('=== CLICKING ADD BUTTON ===')
    page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim().replace(/[\\s\\u00A0]/g, '');
            if (t === 'addAdd' && b.offsetWidth > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return "CLICKED Add";
            }
        }
        return "Add button NOT FOUND";
    }''')
    page.wait_for_timeout(3000)

    print('\n=== CLICKING AWS BUILDER ID OPTION ===')
    clicked = page.evaluate('''() => {
        // Find buttons that contain "AWS Builder ID" text
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim();
            if (t.includes("AWS Builder ID") && b.offsetWidth > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return "CLICKED: " + t.substring(0, 80);
            }
        }
        return "NOT FOUND in buttons";
    }''')
    print(f'  Result: {clicked}')
    page.wait_for_timeout(8000)

    print(f'\n  URL: {page.url}')
    
    # Check for popup windows
    for i, p in enumerate(browser.contexts[0].pages):
        print(f'  Page {i}: {p.url}')

    # Check page content
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    relevant = [l.strip() for l in body.split('\n') if l.strip() and any(w in l.lower() for w in ['email', 'password', 'sign', 'oauth', 'token', 'builder', 'connect', 'login', 'verify', 'code', 'key', 'secret'])]
    print(f'\n=== RELEVANT TEXT ===')
    for l in relevant:
        print(f'  {l}')

    inputs = page.evaluate('''() => {
        const all = document.querySelectorAll('input, select, textarea');
        return Array.from(all).filter(e => e.offsetWidth > 0).map(el => ({
            type: el.type || el.tagName,
            id: el.id,
            name: el.name || '',
            placeholder: el.placeholder || '',
        }));
    }''')
    print(f'\n=== VISIBLE INPUTS ===')
    for inp in inputs:
        print(f'  [{inp["type"]}] id="{inp["id"]}" name="{inp["name"]}" placeholder="{inp["placeholder"]}"')

    buttons = page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        return Array.from(btns).filter(b => b.offsetWidth > 0).map(b => ({
            text: (b.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 100)
        }));
    }''')
    print(f'\n=== VISIBLE BUTTONS ===')
    interesting_btns = [b for b in buttons if any(w in b["text"].lower() for w in ['add', 'builder', 'close', 'submit', 'save', 'connect', 'import', 'key', 'auth'])]
    for b in interesting_btns:
        print(f'  "{b["text"]}"')

    input('\nPress Enter to close...')
