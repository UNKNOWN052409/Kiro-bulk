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
    page.wait_for_timeout(3000)

    # Find all button texts
    buttons = page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        return Array.from(btns).map(b => ({
            text: (b.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 80),
            visible: b.offsetWidth > 0 && b.offsetHeight > 0
        }));
    }''')
    print('\n=== ALL BUTTONS ===')
    for b in buttons:
        if b['visible']:
            print(f'  VISIBLE: "{b["text"]}"')

    # Find the Add button and try clicking it
    print('\n=== CLICKING ADD BUTTON ===')
    clicked = page.evaluate('''() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent || "").trim();
            if (t.includes("Add") && b.offsetWidth > 0) {
                b.scrollIntoView({block: "center"});
                b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return "CLICKED: " + t;
            }
        }
        return "NOT FOUND";
    }''')
    print(f'  Result: {clicked}')
    page.wait_for_timeout(3000)

    # Check what dialog/modal appeared
    dialogs = page.evaluate('''() => {
        const all = [];
        // Check for modal/dialog elements
        const modals = document.querySelectorAll('[role="dialog"], [role="presentation"], .modal, .MuiModal-root, .MuiDialog-root, .MuiPopover-root, .MuiMenu-root, .MuiPaper-root');
        for (const m of modals) {
            if (m.offsetWidth > 0 || m.offsetHeight > 0) {
                all.push({
                    type: m.tagName,
                    role: m.role || '',
                    class: m.className.substring(0, 80),
                    text: (m.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 300),
                    visible: m.offsetWidth > 0 || m.offsetHeight > 0
                });
            }
        }
        return all;
    }''')
    print(f'\n=== DIALOGS/MODALS ({len(dialogs)}) ===')
    for d in dialogs:
        print(f'  [{d["type"]}] role={d["role"]} class={d["class"]}')
        print(f'      text: {d["text"][:200]}')

    # Check all inputs on page
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
    print(f'\n=== ALL INPUTS ({len(inputs)}) ===')
    for inp in inputs:
        if inp['visible']:
            print(f'  [{inp["type"]}] id="{inp["id"]}" name="{inp["name"]}" placeholder="{inp["placeholder"]}" value="{inp["value"]}"')

    # Check all visible text
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    print(f'\n=== PAGE TEXT (bottom 1000) ===')
    print(body[-1000:])

    input('\nPress Enter to close browser...')
