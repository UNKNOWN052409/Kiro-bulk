import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

errors = []

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)
    
    # Capture console messages and errors
    page.on("console", lambda msg: errors.append(f'[CONSOLE {msg.type}] {msg.text}'))
    page.on("pageerror", lambda err: errors.append(f'[PAGE ERROR] {err}'))

    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Login: {r}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)

    # Clear captured errors so far
    errors.clear()

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
    
    # Wait longer for any async content loading
    for sec in range(10):
        page.wait_for_timeout(1000)
        # Check if dialog content appeared
        has_content = page.evaluate('''() => {
            const overlays = document.querySelectorAll('.fixed.inset-0');
            for (const o of overlays) {
                const body = o.querySelector('.p-6');
                if (body && body.children.length > 0) return body.children[0].innerText.substring(0, 200);
            }
            return '';
        }''')
        if has_content:
            print(f'  [t={sec+1}s] Dialog content appeared: {has_content}')
            break
        else:
            print(f'  [t={sec+1}s] Dialog body still empty')
    
    # Print all errors captured
    print(f'\n=== ERRORS/LOGS ({len(errors)}) ===')
    for e in errors[-20:]:
        print(f'  {e}')

    # Try to find any iframe or object
    iframes = page.evaluate('''() => {
        return Array.from(document.querySelectorAll('iframe, object, embed')).map(el => ({
            tag: el.tagName,
            src: el.src || el.data || '',
            visible: el.offsetWidth > 0
        }));
    }''')
    print(f'\n=== IFRAMES/OBJECTS ===')
    for f in iframes:
        print(f'  <{f["tag"]}> src="{f["src"]}" visible={f["visible"]}')

    # Get the full HTML of the dialog body
    dialog_body = page.evaluate('''() => {
        const overlays = document.querySelectorAll('.fixed.inset-0');
        for (const o of overlays) {
            const body = o.querySelector('.p-6');
            if (body) return body.innerHTML.substring(0, 3000);
        }
        return 'N/A';
    }''')
    print(f'\n=== DIALOG BODY HTML ===')
    print(dialog_body[:2000])

    input('\nPress Enter to close...')
