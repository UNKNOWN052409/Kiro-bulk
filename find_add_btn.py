"""Find the Add button on the panel - look for icon buttons or FAB."""
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
        time.sleep(2.0)
        
        page.goto('https://ourproxy.sryze.cc/dashboard/providers/kiro', wait_until='commit', timeout=30000)
        time.sleep(5.0)
        
        for i in range(15):
            time.sleep(2.0)
            count = page.evaluate("document.querySelectorAll('button').length")
            if count > 500:
                break
        
        # Find all buttons including icon-only ones
        all_btns = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('button').forEach(b => {
                const rect = b.getBoundingClientRect();
                const svg = b.querySelector('svg');
                const t = (b.textContent || '').trim();
                const ariaLabel = b.getAttribute('aria-label') || '';
                result.push({
                    text: t.substring(0, 40),
                    ariaLabel: ariaLabel,
                    hasSvg: !!svg,
                    visible: rect.width > 0 && rect.height > 0,
                    x: rect.x, y: rect.y
                });
            });
            return result;
        }""")
        
        # Print all visible buttons (first 100)
        visible = [b for b in all_btns if b['visible']]
        print(f"Total buttons: {len(all_btns)}, visible: {len(visible)}")
        print("\nVisible buttons:")
        for b in visible[:80]:
            print(f"  text='{b['text']}' aria='{b['ariaLabel']}' svg={b['hasSvg']} pos=({b['x']:.0f},{b['y']:.0f})")
        
        page.close()
        context.close()

main()
