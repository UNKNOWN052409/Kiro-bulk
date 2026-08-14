"""Test the panel's built-in device auth flow."""
import time
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        # Login to panel
        page.goto('https://ourproxy.sryze.cc', wait_until='commit', timeout=30000)
        time.sleep(3.0)
        
        # API login
        result = page.evaluate("""async () => {
            const r = await fetch('/api/auth/login', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({password:'7894561230'})
            });
            return {ok: r.ok, status: r.status};
        }""")
        print(f"Panel login: {result}")
        
        if result.get('ok'):
            # Navigate to Kiro provider
            page.goto('https://ourproxy.sryze.cc/dashboard/providers/kiro', wait_until='commit', timeout=30000)
            time.sleep(5.0)
            
            # Wait for page to load
            button_count = 0
            for i in range(20):
                time.sleep(2.0)
                try:
                    button_count = page.evaluate("document.querySelectorAll('button').length")
                except Exception:
                    pass
                if button_count > 100:
                    print(f"Page loaded: {button_count} buttons")
                    break
            
            if button_count <= 100:
                print(f"Page not loaded ({button_count} buttons)")
                page.close(); context.close()
                return
            
            # Click Add button
            clicked = page.evaluate("""() => {
                const btns = document.querySelectorAll('button, [role="button"]');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t === 'add' || t.startsWith('add ')) {
                        if (!t.includes('model') && !t.includes('disable')) {
                            b.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            print(f"Add clicked: {clicked}")
            
            if clicked:
                time.sleep(3.0)
                
                # Click AWS Builder ID
                aws_clicked = page.evaluate("""() => {
                    const btns = document.querySelectorAll('button, [role="button"]');
                    for (const b of btns) {
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('aws builder id') || t.includes('builder id')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                print(f"AWS Builder ID clicked: {aws_clicked}")
                
                if aws_clicked:
                    time.sleep(5.0)
                    
                    # Get the modal URL
                    modal_info = page.evaluate("""() => {
                        const allText = document.body.innerText;
                        const urlMatch = allText.match(/https?:\/\/[^\s"']+awsapps[^\s"']*/);
                        if (urlMatch) {
                            const codeMatch = urlMatch[0].match(/user_code=([A-Z]{4}-[A-Z]{4})/);
                            return {url: urlMatch[0], code: codeMatch ? codeMatch[1] : ''};
                        }
                        return null;
                    }""")
                    
                    if modal_info:
                        print(f"URL: {modal_info['url']}")
                        print(f"Code: {modal_info['code']}")
                    else:
                        print("No URL found in modal")
                        # Show modal text
                        modal_text = page.evaluate("""() => {
                            const modals = document.querySelectorAll('[class*="z-50"], [class*="fixed"], [role="dialog"]');
                            for (const m of modals) {
                                const t = m.innerText || '';
                                if (t && t.length > 10) return t.substring(0, 200);
                            }
                            return document.body.innerText.substring(0, 200);
                        }""")
                        print(f"Modal text: {modal_text[:200]}")
        
        page.close()
        context.close()

main()
