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

    print('\n=== CLICKING ADD ===')
    page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim();
            if (t.includes("Add") && b.offsetWidth > 0 && b.offsetHeight > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return "CLICKED";
            }
        }
        return "NOT FOUND";
    }''')
    page.wait_for_timeout(3000)

    # Now find and click the AWS Builder ID option in the dialog
    print('\n=== CLICKING AWS BUILDER ID ===')
    clicked = page.evaluate('''() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const t = (el.textContent || "").trim();
            if (el.offsetWidth > 0 && el.offsetHeight > 0 && t.includes("AWS Builder ID")) {
                el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return "CLICKED on <" + el.tagName + "> class=" + (el.className || "").substring(0, 60);
            }
        }
        return "NOT FOUND";
    }''')
    print(f'  Result: {clicked}')
    page.wait_for_timeout(5000)

    # Check URL
    print(f'\n  URL: {page.url}')
    
    # Check for new windows/pages
    for i, p in enumerate(browser.contexts[0].pages):
        print(f'  Page {i}: {p.url}')

    # Check what's on screen now
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    # Find relevant lines
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    print(f'\n=== RELEVANT PAGE TEXT ===')
    for l in lines:
        if any(w in l.lower() for w in ['connect', 'builder', 'iam', 'api key', 'token', 'email', 'password', 'sign', 'oauth', 'login']):
            print(f'  {l}')

    # Get all visible inputs
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

    # Check all visible buttons
    buttons = page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        return Array.from(btns).filter(b => b.offsetWidth > 0).map(b => ({
            text: (b.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 80)
        }));
    }''')
    print(f'\n=== VISIBLE BUTTONS ===')
    for b in buttons:
        print(f'  "{b["text"]}"')

    input('\nPress Enter to close...')
