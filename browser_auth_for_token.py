"""
Browser auth to complete device flow started by token_capture_test.py.
Reads /tmp/device_auth_info.json for the user code and email.
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

def main():
    # Read device auth info
    with open('/tmp/device_auth_info.json') as f:
        auth_info = json.load(f)
    
    user_code = auth_info['user_code']
    email = auth_info['email']
    print(f"[*] User Code: {user_code}, Email: {email}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        page.set_default_timeout(30000)
        
        # Navigate to device auth
        url = f'https://view.awsapps.com/start/#/device?user_code={user_code}'
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
                    time.sleep(3.0)
            except Exception:
                try:
                    accept = page.locator('button:has-text("Accept")').first
                    if accept.is_visible(timeout=3000):
                        accept.click()
                        time.sleep(3.0)
                except Exception:
                    pass
        
        # Click Continue on device page
        try:
            continue_btn = page.locator('button:has-text("Continue")').first
            if continue_btn.is_visible(timeout=5000):
                continue_btn.click()
                print("  [+] Device page Continue clicked")
        except Exception:
            pass
        time.sleep(8.0)
        
        # Fill email
        print("[*] Filling email...")
        try:
            email_input = page.locator('input:not([type="password"]):visible').first
            if email_input.is_visible(timeout=5000):
                email_input.fill(email)
                email_input.press('Enter')
                print("  [+] Email filled")
        except Exception as e:
            print(f"  [!] Email: {e}")
        time.sleep(10.0)
        
        # Check state
        body_text = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email: {body_text[:150]}")
        
        # Handle name page
        if 'enter your name' in body_text:
            print("[*] On name page...")
            success = False
            for name in ['John Smith', 'Test User', 'AWS User', 'Demo Account', 'New User']:
                try:
                    name_input = page.locator('input:not([type="password"]):visible').first
                    if name_input.is_visible(timeout=5000):
                        name_input.fill(name)
                        time.sleep(0.5)
                        
                        continue_btn = page.locator('button:has-text("Continue")').first
                        if continue_btn.is_visible(timeout=5000):
                            continue_btn.click()
                            print(f"  [+] Continue with '{name}'")
                            time.sleep(8.0)
                            
                            body_text = page.evaluate("document.body.innerText").lower()
                            if 'enter your name' not in body_text:
                                print("  [+] Moved past name page!")
                                success = True
                                break
                            elif 'err-837' in body_text:
                                print(f"  [!] ERR-837 with '{name}'")
                except Exception as e:
                    print(f"  [!] Attempt with '{name}': {e}")
            
            if not success:
                print("[!] Failed to pass name page")
                page.close()
                return
        
        # OTP
        if 'verify your email' in body_text:
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            time.sleep(15.0)
            otp = extract_otp_gmail(email, timeout=30, after_timestamp=otp_arrival)
            if otp:
                print(f"  [+] OTP: {otp}")
                try:
                    otp_input = page.locator('input:not([type="password"]):visible').first
                    if otp_input.is_visible(timeout=5000):
                        otp_input.fill(otp)
                        otp_input.press('Enter')
                        time.sleep(8.0)
                except Exception as e:
                    print(f"  [!] OTP: {e}")
                
                # Confirm
                try:
                    confirm_btn = page.locator('button:has-text("Confirm")').first
                    if confirm_btn.is_visible(timeout=5000):
                        confirm_btn.click()
                        print("  [+] Confirm clicked")
                        time.sleep(8.0)
                except Exception:
                    pass
                
                # Allow
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
        
        # Final
        time.sleep(5.0)
        body_text = page.evaluate("document.body.innerText").lower()
        print(f"[*] Final: {body_text[:300]}")
        page.close()

if __name__ == '__main__':
    main()
