"""Find the Add button on the panel."""
import time
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto('https://ourproxy.sryze.cc', wait_until='commit', timeout=30000)
        time.sleep(3.0)
        page.evaluate("""async () => {
            await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password:'7894561230'})});
        }""")
        
        page.goto('https://ourproxy.sryze.cc/dashboard/providers/kiro', wait_until='commit', timeout=30000)
        time.sleep(5.0)
        
        # List all buttons with their text
        btns = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('button, [role="button"]').forEach(b => {
                const t = (b.textContent || '').trim();
                if (t && t.length < 30 && (t.toLowerCase().includes('add') || t.toLowerCase().includes('new') || t.toLowerCase().includes('connect'))) {
                    result.push(t);
                }
            });
            return [...new Set(result)];
        }""")
        print(f"Buttons: {btns[:20]}")
        
        page.close()
        context.close()

main()
