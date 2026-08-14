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

    # Click the Add button
    print('=== CLICKING ADD ===')
    page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim();
            if (t.includes("Add") && b.offsetWidth > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return true;
            }
        }
        return false;
    }''')
    page.wait_for_timeout(2000)

    # Check what's on the page now
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    print(f'\n=== DIALOG TEXT ===')
    # Find the dialog text
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    for l in lines:
        if any(w in l.lower() for w in ['connect', 'builder', 'iam', 'key', 'token', 'import', 'auth']):
            print(f'  {l}')

    # Now click "AWS Builder ID"
    print('\n=== CLICKING AWS BUILDER ID ===')
    clicked = page.evaluate('''() => {
        const all = document.querySelectorAll('button, div, [role="button"], span');
        for (const el of all) {
            const t = (el.textContent || "").trim();
            if (t.includes("AWS Builder ID") && el.offsetWidth > 0) {
                el.scrollIntoView({block: "center"});
                el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                console.log("CLICKED AWS Builder ID");
                return true;
            }
        }
        return false;
    }''')
    print(f'  AWS Builder ID clicked: {clicked}')
    page.wait_for_timeout(5000)

    # Check for new content - inputs, dialog
    inputs = page.evaluate('''() => {
        const all = document.querySelectorAll('input, select, textarea');
        return Array.from(all).map(el => ({
            type: el.type || el.tagName,
            id: el.id,
            name: el.name || '',
            placeholder: el.placeholder || '',
            visible: el.offsetWidth > 0 && el.offsetHeight > 0,
            value: el.value || ''
        }));
    }''')
    print(f'\n=== INPUTS AFTER CLICK ({len(inputs)}) ===')
    for inp in inputs:
        if inp['visible']:
            print(f'  [{inp["type"]}] id="{inp["id"]}" name="{inp["name"]}" placeholder="{inp["placeholder"]}" value="{inp["value"]}"')

    body2 = page.evaluate("() => document.body ? document.body.innerText : ''")
    print(f'\n=== FULL PAGE TEXT ===')
    print(body2)

    # Get all visible interactive elements
    interactive = page.evaluate('''() => {
        const els = document.querySelectorAll('button, a, input, select, [role="button"]');
        return Array.from(els).filter(e => e.offsetWidth > 0).map(e => ({
            tag: e.tagName,
            text: (e.textContent || "").trim().substring(0, 80),
            type: e.type || ''
        }));
    }''')
    print(f'\n=== VISIBLE INTERACTIVE ELEMENTS ===')
    for el in interactive:
        print(f'  <{el["tag"]}> type="{el["type"]}" text="{el["text"]}"')

    input('Press Enter to close...')
