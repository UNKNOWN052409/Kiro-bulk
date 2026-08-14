"""
Try typing name character by character with keyboard.type()
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
        
        # Fill email
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            time.sleep(0.5)
            inp.fill(EMAIL)
            time.sleep(0.5)
            inp.press('Enter')
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(12.0)
        
        # Check and handle name
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] Body after email: {body[:150]}")
        
        if 'enter your name' in body:
            print("[*] Typing name character by character...")
            for name in ['John Smith', 'Jane Doe', 'Test Account']:
                try:
                    inp = page.locator('input:not([type="password"]):visible').first
                    inp.click()
                    time.sleep(1.0)
                    # Clear existing value
                    inp.press('Control+a')
                    time.sleep(0.5)
                    inp.press('Backspace')
                    time.sleep(0.5)
                    # Type slowly
                    inp.type(name, delay=100)
                    time.sleep(1.0)
                    current = inp.input_value()
                    print(f"  [*] Typed '{name}', value: '{current}'")
                    
                    # Click Continue
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    time.sleep(10.0)
                    
                    body = page.evaluate("document.body.innerText").lower()
                    if 'enter your name' not in body:
                        print(f"  [+] SUCCESS with '{name}'!")
                        break
                    elif 'err-837' in body:
                        print(f"  [!] ERR-837 with '{name}'")
                    else:
                        print(f"  [!] Still on name page")
                except Exception as e:
                    print(f"  [!] Failed with '{name}': {e}")
            
            body = page.evaluate("document.body.innerText").lower()
            if 'enter your name' in body:
                print("[!] All name attempts failed")
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
                
                # Confirm
                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    time.sleep(8.0)
                except Exception: pass
                
                # Allow
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
    
    proc.wait(timeout=120)
    print(f"[*] kiro-cli exit code: {proc.returncode}")

if __name__ == '__main__':
    main()
