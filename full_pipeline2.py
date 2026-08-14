"""
Full pipeline v2: kiro-cli login -> browser auth -> OTP -> allow -> token
Improved OTP handling with longer waits and retries.
"""
import sys, os, time, subprocess, re, json
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

def handle_cookies(page):
    body = page.evaluate("document.body.innerText").lower()
    if 'cookie preferences' in body or 'essential cookies' in body:
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            try:
                page.locator('button:has-text("Accept")').first.click(timeout=3000)
            except Exception:
                pass
        time.sleep(5.0)
        return True
    return False

def get_state(page):
    body = page.evaluate("document.body.innerText").lower()
    return {
        'body': body,
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body,
        'onAllow': 'allow' in body,
        'onErr': 'err-837' in body,
    }

def add_account_to_panel(refresh_token, email):
    """Add account to 9Router panel via API."""
    import requests
    session = requests.Session()
    
    resp = session.post("https://ourproxy.sryze.cc/api/auth/login",
                       json={"password": "7894561230"}, timeout=10)
    if not resp.ok:
        print(f"  [!] Panel login failed: {resp.status_code}")
        return False
    
    resp = session.post("https://ourproxy.sryze.cc/api/oauth/kiro/import",
                       json={
                           "refreshToken": refresh_token,
                           "region": "us-east-1",
                           "authMethod": "builder-id",
                           "startUrl": "https://view.awsapps.com/start",
                           "name": email
                       }, timeout=30)
    
    if resp.ok:
        print(f"  [+] Account added to panel: {email}")
        return True
    else:
        print(f"  [!] Panel import failed: {resp.status_code} {resp.text[:200]}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 full_pipeline2.py <email> [refresh_token]")
        return
    
    email = sys.argv[1]
    name = email.split('@')[0]
    print(f"[*] Adding account: {email}")
    
    # Start kiro-cli login
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
        print("[!] No code from kiro-cli")
        proc.kill()
        return
    
    print(f"[*] User Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        # Device page
        page.goto(f'https://view.awsapps.com/start/#/device?user_code={code}',
                  wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        handle_cookies(page)
        
        # Continue
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(8.0)
        handle_cookies(page)
        
        # Fill email
        inp = page.locator('input:not([type="password"]):visible').first
        inp.click()
        inp.press('Control+a')
        inp.press('Backspace')
        inp.fill(email)
        inp.press('Enter')
        time.sleep(12.0)
        handle_cookies(page)
        
        state = get_state(page)
        print(f"[*] After email: onName={state['onName']}, onOtp={state['onOtp']}")
        
        # Name page
        if state['onName']:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.type(name.title(), delay=100)
            time.sleep(1.0)
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
            time.sleep(10.0)
            
            state = get_state(page)
            # ERR-837 retry
            if state['onErr']:
                print("[!] ERR-837 - waiting 30s and retrying...")
                time.sleep(30)
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.type(name.title(), delay=100)
                time.sleep(1.0)
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                time.sleep(10.0)
                state = get_state(page)
            
            if state['onErr']:
                print("[!] ERR-837 persists - aborting")
                page.close(); context.close(); proc.kill()
                return
            print(f"[*] After name: onOtp={state['onOtp']}")
        
        # OTP
        if state['onOtp']:
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            
            # Wait longer for OTP email
            time.sleep(25.0)
            
            otp = None
            for attempt in range(5):
                otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival)
                if otp:
                    break
                print(f"  [*] OTP not found (attempt {attempt+1}/5), waiting 10s...")
                time.sleep(10.0)
            
            if not otp:
                # Try resend
                print("[!] No OTP after 5 attempts - trying resend...")
                try:
                    page.locator('button:has-text("Resend")').first.click(timeout=5000)
                    print("  [+] Resend clicked")
                    time.sleep(30.0)
                    otp_arrival = time.time()
                    for attempt in range(5):
                        otp = extract_otp_gmail(email, timeout=10, after_timestamp=otp_arrival)
                        if otp:
                            break
                        time.sleep(10.0)
                except Exception as e:
                    print(f"[!] Resend error: {e}")
            
            if otp:
                print(f"  [+] OTP: {otp}")
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.fill(otp)
                inp.press('Enter')
                time.sleep(8.0)
            else:
                print("[!] No OTP received - aborting")
                page.close(); context.close(); proc.kill()
                return
            
            # Confirm
            try:
                page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                print("  [+] Confirm clicked")
                time.sleep(8.0)
            except Exception: pass
            
            state = get_state(page)
            
            # Allow
            if state['onAllow']:
                page.locator('button:has-text("Allow")').first.click(timeout=5000)
                print("  [+] Allow clicked")
                time.sleep(10.0)
        
        page.close()
        context.close()
    
    # Wait for kiro-cli
    print("[*] Waiting for kiro-cli to complete...")
    for i in range(120):
        if proc.poll() is not None:
            if proc.returncode == 0:
                print("[+] kiro-cli login SUCCESS!")
            else:
                print(f"[!] kiro-cli exited with code {proc.returncode}")
            break
        time.sleep(1)
    
    if proc.poll() is None:
        print("[!] kiro-cli still running after 120s - killing")
        proc.kill()

if __name__ == '__main__':
    main()
