"""
Full pipeline: kiro-cli login -> browser auth -> OTP -> allow -> capture token
Uses kiro-cli which captures the token when login succeeds.
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
    
    # Login to panel
    resp = session.post("https://ourproxy.sryze.cc/api/auth/login",
                       json={"password": "7894561230"}, timeout=10)
    if not resp.ok:
        print(f"  [!] Panel login failed: {resp.status_code}")
        return False
    
    # Import token
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
        print("Usage: python3 full_pipeline.py <email>")
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
        
        # Navigate to device page
        page.goto(f'https://view.awsapps.com/start/#/device?user_code={code}',
                  wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        handle_cookies(page)
        
        # Continue on device page
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
            if state['onErr']:
                print("[!] ERR-837 - retrying after 30s...")
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
            print(f"[*] After name: onOtp={state['onOtp']}, onAllow={state['onAllow']}")
        
        # OTP
        if state['onOtp']:
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            time.sleep(15.0)
            otp = extract_otp_gmail(email, timeout=30, after_timestamp=otp_arrival)
            if otp:
                print(f"  [+] OTP: {otp}")
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.fill(otp)
                inp.press('Enter')
                time.sleep(8.0)
            else:
                print("[!] No OTP received - trying resend...")
                try:
                    page.locator('button:has-text("Resend")').first.click(timeout=5000)
                    time.sleep(20.0)
                    otp_arrival = time.time()
                    otp = extract_otp_gmail(email, timeout=30, after_timestamp=otp_arrival)
                    if otp:
                        print(f"  [+] OTP (retry): {otp}")
                        inp = page.locator('input:not([type="password"]):visible').first
                        inp.click()
                        inp.fill(otp)
                        inp.press('Enter')
                        time.sleep(8.0)
                    else:
                        print("[!] No OTP after resend")
                        page.close(); context.close(); proc.kill()
                        return
                except Exception: pass
            
            # Click Confirm
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
        
        # Wait for kiro-cli to complete
        print("[*] Waiting for kiro-cli to complete...")
        page.close()
        context.close()
    
    # Wait for kiro-cli with longer timeout
    success = False
    for i in range(60):
        try:
            proc.wait(timeout=2)
            if proc.returncode == 0:
                print("[+] kiro-cli login SUCCESS!")
                success = True
            else:
                print(f"[!] kiro-cli exited with code {proc.returncode}")
            break
        except subprocess.TimeoutExpired:
            # Check if still running
            if proc.poll() is not None:
                if proc.returncode == 0:
                    print("[+] kiro-cli login SUCCESS!")
                    success = True
                else:
                    print(f"[!] kiro-cli exited with code {proc.returncode}")
                break
            time.sleep(1)
    
    if success:
        # Try to find the kiro-cli secret store
        home = os.path.expanduser('~')
        # Check common locations
        possible_paths = [
            f'{home}/.config/kiro-cli',
            f'{home}/.kiro-cli',
            f'{home}/.config/kiro',
            f'{home}/.kiro',
        ]
        found = False
        for p in possible_paths:
            if os.path.exists(p):
                print(f"  [+] Found kiro config dir: {p}")
                for root, dirs, files in os.walk(p):
                    for f in files:
                        print(f"    - {os.path.join(root, f)}")
                found = True
        
        # Also check if kiro-cli stores tokens in a known location
        if not found:
            print("  [!] No kiro config dir found - token might be in memory")

if __name__ == '__main__':
    main()
