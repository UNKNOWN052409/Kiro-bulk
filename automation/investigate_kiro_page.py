import sys, json
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

with Camoufox(geoip=True, humanize=True, headless=True, os='windows') as browser:
    page = browser.new_page()
    page.set_default_timeout(30000)
    
    # Login to local panel - first go to the page
    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return resp.ok; }')
    print(f'Login: {r}')
    
    # Go to Kiro provider page
    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(3000)
    print(f'Kiro page URL: {page.url}')
    
    body = page.evaluate("() => document.body ? document.body.innerText : ''")
    print(f'\n=== PAGE TEXT ===\n{body[:2000]}')
    
    # Get interactive elements
    interactive = page.evaluate('''() => {
        const els = document.querySelectorAll('button, a, input, select, [role="button"], textarea');
        return Array.from(els).map(e => ({
            tag: e.tagName,
            type: e.type || '',
            text: (e.textContent || '').trim().substring(0, 60),
            id: e.id,
            name: e.name || '',
            placeholder: e.placeholder || '',
            href: e.href || ''
        }));
    }''')
    print('\n=== INTERACTIVE ELEMENTS ===')
    for el in interactive:
        print(f'  <{el["tag"]}> id="{el["id"]}" name="{el["name"]}" placeholder="{el["placeholder"]}" text="{el["text"]}"')
    
    screenshot = page.screenshot(full_page=True)
    with open(r'C:\Users\Unkno\Videos\New folder\automation (2)\kiro_page.png', 'wb') as f:
        f.write(screenshot)
    print('\nScreenshot saved')
