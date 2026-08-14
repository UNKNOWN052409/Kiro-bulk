"""List ALL buttons on the panel."""
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
        
        # List first 50 buttons
        btns = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('button').forEach(b => {
                const t = (b.textContent || '').trim();
                if (t) result.push(t);
            });
            return [...new Set(result)].slice(0, 50);
        }""")
        print(f"Buttons ({len(btns)}):")
        for b in btns:
            print(f"  '{b}'")
        
        # Also check SVG icons in buttons
        svg_btns = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('button').forEach(b => {
                const svg = b.querySelector('svg');
                const t = (b.textContent || '').trim();
                result.push({text: t.substring(0, 30), hasSvg: !!svg, ariaLabel: b.getAttribute('aria-label') || ''});
            });
            return result.filter(b => !b.text && b.hasSvg).slice(0, 20);
        }""")
        print(f"\nSVG-only buttons: {svg_btns}")
        
        page.close()
        context.close()

main()
