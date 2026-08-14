import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

with Camoufox(geoip=True, humanize=True, headless=True, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)

    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Login: {r}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)

    # Get the FULL HTML to find dialog-related elements
    html = page.evaluate("() => document.documentElement ? document.documentElement.outerHTML : ''")
    
    # Search for "Connect Kiro" in the HTML
    if 'Connect Kiro' in html:
        print('Found "Connect Kiro" in HTML')
    if 'AWS Builder ID' in html:
        print('Found "AWS Builder ID" in HTML')
    if 'authentication' in html.lower():
        print('Found "authentication" in HTML')
    
    # Find dialog/modal related divs
    dialog_html = page.evaluate('''() => {
        const results = [];
        const all = document.querySelectorAll('div, section, aside');
        for (const el of all) {
            const t = (el.textContent || "").trim();
            if ((t.includes("Connect Kiro") || t.includes("AWS Builder ID")) && t.length < 500) {
                results.push({
                    tag: el.tagName,
                    id: el.id,
                    class: (el.className || "").substring(0, 100),
                    style: el.getAttribute("style") || "",
                    text: t.substring(0, 300),
                    visible: el.offsetWidth > 0 && el.offsetHeight > 0
                });
            }
        }
        return results;
    }''')
    print(f'\n=== DIALOG ELEMENTS ({len(dialog_html)}) ===')
    for d in dialog_html:
        print(f'  [{d["tag"]}] id="{d["id"]}" visible={d["visible"]}')
        print(f'      class="{d["class"]}"')
        print(f'      style="{d["style"]}"')
        print(f'      text="{d["text"]}"')

    # If dialog is not visible, try clicking Add and see what changes
    print('\n=== CLICKING ADD ===')
    page.evaluate('''() => {
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
    page.wait_for_timeout(5000)
    
    # Check again for dialog
    dialog_html2 = page.evaluate('''() => {
        const results = [];
        const all = document.querySelectorAll('div, section, aside');
        for (const el of all) {
            const t = (el.textContent || "").trim();
            if ((t.includes("Connect Kiro") || t.includes("AWS Builder ID")) && t.length < 500) {
                results.push({
                    tag: el.tagName,
                    id: el.id,
                    class: (el.className || "").substring(0, 100),
                    text: t.substring(0, 300),
                    visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                    style: el.getAttribute("style") || ""
                });
            }
        }
        return results;
    }''')
    print(f'\n=== DIALOG ELEMENTS AFTER CLICK ({len(dialog_html2)}) ===')
    for d in dialog_html2:
        print(f'  [{d["tag"]}] id="{d["id"]}" visible={d["visible"]}')
        print(f'      class="{d["class"]}"')
        print(f'      text="{d["text"]}"')

    # Check for popups/new windows
    print(f'\n  Pages: {len(browser.context.pages)}')
    for i, p in enumerate(browser.context.pages):
        print(f'  Page {i}: {p.url}')
    
    # Check for iframes
    iframes = page.evaluate('''() => {
        const frames = document.querySelectorAll('iframe');
        return Array.from(frames).map(f => ({src: f.src, id: f.id}));
    }''')
    print(f'\n  Iframes: {len(iframes)}')
    for f in iframes:
        print(f'    {f}')

    # Monitor network requests for potential API calls
    print('\n=== TRYING API DIRECTLY ===')
    apis = page.evaluate('''async () => {
        const results = [];
        // Try common endpoints
        for (const path of ['/api/providers/kiro', '/api/providers', '/api/kiro', '/api/connections']) {
            try {
                const r = await fetch(path);
                const text = await r.text();
                results.push({path, status: r.status, body: text.substring(0, 200)});
            } catch(e) {
                results.push({path, error: e.message});
            }
        }
        return results;
    }''')
    for a in apis:
        print(f'  {a["path"]}: status={a.get("status","?")} body={a.get("body","")[:100]}')

    print('\nDone - check output above')
