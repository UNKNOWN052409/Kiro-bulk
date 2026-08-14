"""
Try submitting the name form via JS form.submit() instead of button click.
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

EMAIL = 'ax3p0kzyk6@havenhaus.in'

def main():
    proc = subprocess.Popen(
        ['kiro-cli', 'login', '--use-device-flow', '--license', 'free'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    code = None
    for i in range(30):
        line = proc.stdout.readline()
        if not line: break
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', line.strip())
        if 'Code:' in stripped:
            code = stripped.split('Code:')[1].strip()
            break
        time.sleep(1)
    
    if not code:
        print("[!] No code"); proc.kill(); return
    
    print(f"[*] Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # Handle cookies
        body = page.evaluate("document.body.innerText").lower()
        if 'cookie' in body:
            try:
                page.locator('button:has-text("Decline")').first.click(timeout=3000)
            except Exception:
                try:
                    page.locator('button:has-text("Accept")').first.click(timeout=3000)
                except Exception:
                    pass
            time.sleep(3.0)
        
        # Continue on device page
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(8.0)
        
        # Fill email and submit
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.fill(EMAIL)
            inp.press('Enter')
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(12.0)
        
        body = page.evaluate("document.body.innerText").lower()
        if 'enter your name' not in body:
            print(f"[!] Not on name page: {body[:200]}")
            page.close(); proc.kill(); return
        
        print("[*] On name page - trying form.submit() approach...")
        
        # Fill name and submit form directly
        result = page.evaluate("""() => {
            const inputs = document.querySelectorAll('input');
            let nameInput = null;
            for (const inp of inputs) {
                const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                if (!vis) continue;
                const type = (inp.type || '').toLowerCase();
                if (type === 'text') {
                    nameInput = inp;
                    break;
                }
            }
            if (!nameInput) return {error: 'No name input found'};
            
            // Fill the name
            nameInput.focus();
            nameInput.value = '';
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            s.call(nameInput, 'John Smith');
            nameInput.dispatchEvent(new Event('input', {bubbles: true}));
            nameInput.dispatchEvent(new Event('change', {bubbles: true}));
            
            // Find the form and submit it
            const form = nameInput.closest('form');
            if (form) {
                form.submit();
                return {success: true, method: 'form.submit()'};
            }
            
            // If no form, try clicking Continue
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                if (!vis) continue;
                const t = (b.textContent || '').trim().toLowerCase();
                if (t.includes('continue')) {
                    b.click();
                    return {success: true, method: 'button.click()'};
                }
            }
            return {error: 'No form or button found'};
        }""")
        
        print(f"[*] Submit result: {result}")
        time.sleep(12.0)
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After submit: {body[:300]}")
        
        # If still on name page with ERR-837, try one more approach:
        # Fill name via keyboard, wait longer, then click
        if 'enter your name' in body and 'err-837' in body:
            print("[*] ERR-837 again - trying slower approach with real keyboard...")
            time.sleep(5.0)
            
            # Click on the name input
            try:
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                time.sleep(2.0)
                
                # Type name slowly
                inp.type('John Smith', delay=200)
                time.sleep(3.0)
                
                # Use keyboard Tab to move to button, then Enter
                inp.press('Tab')
                time.sleep(1.0)
                inp.press('Enter')
                time.sleep(12.0)
                
                body = page.evaluate("document.body.innerText").lower()
                print(f"[*] After keyboard submit: {body[:300]}")
            except Exception as e:
                print(f"[!] Keyboard approach failed: {e}")
        
        # Check final state
        if 'enter your name' in body:
            print("[!] Still on name page")
            page.close(); proc.kill(); return
        
        # OTP
        if 'verify your email' in body:
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            time.sleep(15.0)
            otp = extract_otp_gmail(EMAIL, timeout=30, after_timestamp=otp_arrival)
            if otp:
                print(f"  [+] OTP: {otp}")
                try:
                    inp = page.locator('input:not([type="password"]):visible').first
                    inp.click()
                    inp.fill(otp)
                    inp.press('Enter')
                    time.sleep(8.0)
                except Exception: pass
                
                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    time.sleep(8.0)
                except Exception: pass
                
                body = page.evaluate("document.body.innerText").lower()
                if 'allow' in body:
                    try:
                        page.locator('button:has-text("Allow")').first.click(timeout=5000)
                        time.sleep(10.0)
                    except Exception: pass
        
        time.sleep(5.0)
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] Final: {body[:300]}")
        page.close()
    
    proc.wait(timeout=60)
    print(f"[*] kiro-cli exit: {proc.returncode}")

if __name__ == '__main__':
    main()
