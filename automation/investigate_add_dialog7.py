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
    page.wait_for_timeout(5000)

    # Get the FULL dialog content
    dialog_info = page.evaluate('''() => {
        // Find the fixed overlay dialog container
        const overlays = document.querySelectorAll('.fixed.inset-0');
        for (const overlay of overlays) {
            if (overlay.offsetWidth > 0 || overlay.offsetHeight > 0) {
                return {
                    visible: overlay.offsetWidth > 0,
                    html: overlay.outerHTML.substring(0, 5000),
                    text: overlay.innerText.substring(0, 2000)
                };
            }
        }
        return {visible: false, html: '', text: 'No overlay found'};
    }''')
    
    print(f'\n=== DIALOG VISIBLE: {dialog_info["visible"]} ===')
    print(f'\n=== DIALOG TEXT ===')
    print(dialog_info["text"])
    print(f'\n=== DIALOG HTML (first 3000) ===')
    print(dialog_info["html"][:3000])

    # Also get all visible elements in the dialog area
    elements = page.evaluate('''() => {
        const results = [];
        const overlays = document.querySelectorAll('.fixed.inset-0');
        for (const overlay of overlays) {
            const all = overlay.querySelectorAll('*');
            for (const el of all) {
                if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                    const tag = el.tagName;
                    const text = (el.textContent || "").trim().replace(/\\s+/g, " ").substring(0, 60);
                    const cls = (el.className || "").substring(0, 60);
                    if (tag !== 'DIV' || text) {
                        results.push({tag, text, cls, type: el.type || ''});
                    }
                }
            }
        }
        return results;
    }''')
    
    print(f'\n=== DIALOG ELEMENTS ({len(elements)}) ===')
    for el in elements[:50]:  # limit output
        print(f'  <{el["tag"]}> type="{el["type"]}" class="{el["cls"]}" text="{el["text"]}"')

    input('\nPress Enter to close...')
