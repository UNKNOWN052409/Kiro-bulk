"""
Kiro CLI Login with NATIVE Playwright methods (fill/click instead of JS evaluate).
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
        print("[!] No code received")
        proc.kill()
        return
    
    print(f"[*] User Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        page.set_default_timeout(30000)
        
        # Navigate to device auth
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        print(f"[*] Navigating to device page...")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # Handle cookie page if present
        body_text = page.evaluate("document.body.innerText").lower()
        if 'cookie' in body_text:
            print("[*] Handling cookie preferences...")
            try:
                decline = page.locator('button:has-text("Decline")').first
                if decline.is_visible(timeout=3000):
                    decline.click()
                    print("  [+] Declined cookies")
                    time.sleep(3.0)
            except Exception:
                try:
                    accept = page.locator('button:has-text("Accept")').first
                    if accept.is_visible(timeout=3000):
                        accept.click()
                        print("  [+] Accepted cookies")
                        time.sleep(3.0)
                except Exception:
                    pass
        
        # Click Continue on device page
        print("[*] Clicking Continue on device page...")
        try:
            continue_btn = page.locator('button:has-text("Continue")').first
            if continue_btn.is_visible(timeout=5000):
                continue_btn.click()
                print("  [+] Continue clicked")
        except Exception as e:
            print(f"  [!] Continue button: {e}")
        time.sleep(8.0)
        
        # Fill email using native fill
        print("[*] Filling email...")
        try:
            email_input = page.locator('input:not([type="password"]):visible').first
            if email_input.is_visible(timeout=5000):
                email_input.fill(EMAIL)
                email_input.press('Enter')
                print("  [+] Email filled and Enter pressed")
        except Exception as e:
            print(f"  [!] Email fill: {e}")
        time.sleep(10.0)
        
        # Check state
        body_text = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email - body: {body_text[:200]}")
        
        # Handle name page with native methods
        if 'enter your name' in body_text:
            print("[*] On name page - using native fill...")
            for attempt, name in enumerate(['John Smith', 'Test User', 'AWS User']):
                try:
                    # Clear the name field first
                    name_input = page.locator('input:not([type="password"]):visible').first
                    if name_input.is_visible(timeout=5000):
                        name_input.fill('')
                        time.sleep(0.5)
                        name_input.fill(name)
                        time.sleep(0.5)
                        current = name_input.input_value()
                        print(f"  [*] Name value: '{current}'")
                        
                        # Click Continue
                        continue_btn = page.locator('button:has-text("Continue")').first
                        if continue_btn.is_visible(timeout=5000):
                            continue_btn.click()
                            print(f"  [+] Continue clicked (attempt {attempt+1})")
                            time.sleep(8.0)
                            
                            body_text = page.evaluate("document.body.innerText").lower()
                            if 'enter your name' not in body_text:
                                print(f"  [+] Moved past name page!")
                                break
                            elif 'err-837' in body_text:
                                print(f"  [!] ERR-837 on attempt {attempt+1}")
                            else:
                                print(f"  [!] Still on name page (attempt {attempt+1})")
                except Exception as e:
                    print(f"  [!] Name attempt {attempt+1} failed: {e}")
            
            # Check final state
            body_text = page.evaluate("document.body.innerText").lower()
            if 'enter your name' in body_text:
                print("[!] Still on name page after all attempts")
                page.close()
                proc.kill()
                return
        
        # OTP
        if 'verify your email' in body_text:
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            time.sleep(15.0)
            otp = extract_otp_gmail(EMAIL, timeout=30, after_timestamp=otp_arrival)
            if otp:
                print(f"  [+] OTP: {otp}")
                try:
                    otp_input = page.locator('input:not([type="password"]):visible').first
                    if otp_input.is_visible(timeout=5000):
                        otp_input.fill(otp)
                        otp_input.press('Enter')
                        print("  [+] OTP submitted")
                        time.sleep(8.0)
                except Exception as e:
                    print(f"  [!] OTP submit: {e}")
                
                # Click Confirm
                try:
                    confirm_btn = page.locator('button:has-text("Confirm")').first
                    if confirm_btn.is_visible(timeout=5000):
                        confirm_btn.click()
                        print("  [+] Confirm clicked")
                        time.sleep(8.0)
                except Exception:
                    pass
                
                # Click Allow
                body_text = page.evaluate("document.body.innerText").lower()
                if 'allow' in body_text:
                    try:
                        allow_btn = page.locator('button:has-text("Allow")').first
                        if allow_btn.is_visible(timeout=5000):
                            allow_btn.click()
                            print("  [+] Allow clicked")
                            time.sleep(10.0)
                    except Exception:
                        pass
        
        # Final state
        time.sleep(5.0)
        body_text = page.evaluate("document.body.innerText").lower()
        print(f"[*] Final body: {body_text[:300]}")
        page.close()
    
    # Wait for kiro-cli
    print("[*] Waiting for kiro-cli...")
    try:
        proc.wait(timeout=120)
        if proc.returncode == 0:
            print("[+] kiro-cli login SUCCEEDED!")
            # Look for secret store
            home = os.path.expanduser('~')
            for root, dirs, files in os.walk(home):
                for f in files:
                    if 'kiro' in f.lower() and ('secret' in f.lower() or 'token' in f.lower() or 'auth' in f.lower()):
                        print(f"  [+] Found: {os.path.join(root, f)}")
        else:
            print(f"[!] kiro-cli exited with code {proc.returncode}")
    except subprocess.TimeoutExpired:
        print("[!] kiro-cli still running")
        proc.kill()
        proc.wait()

if __name__ == '__main__':
    main()
