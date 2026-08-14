"""
Test with a completely fresh browser profile (new user-data-dir).
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

EMAIL = 'ax3p0kzyk6@havenhaus.in'

def main():
    # Start a fresh Chrome with a new profile
    fresh_profile = '/tmp/fresh_chrome_profile'
    os.makedirs(fresh_profile, exist_ok=True)
    
    proc = subprocess.Popen(
        [
            'chromium', '--no-sandbox', '--disable-dev-shm-usage',
            '--headless=new', '--disable-gpu', '--no-first-run',
            '--disable-extensions', '--disable-plugins',
            '--user-data-dir=' + fresh_profile,
            '--remote-debugging-port=9333',
            '--remote-debugging-address=127.0.0.1',
            '--disable-background-networking',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--metrics-recording-only',
            '--no-default-browser-check',
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    
    time.sleep(5)
    
    # Verify Chrome is running
    result = subprocess.run(
        ['curl', '-s', 'http://127.0.0.1:9333/json/version'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("[!] Fresh Chrome not responding on 9333")
        proc.kill()
        return
    
    print("[+] Fresh Chrome running on port 9333")
    
    # Start kiro-cli
    cli_proc = subprocess.Popen(
        ['kiro-cli', 'login', '--use-device-flow', '--license', 'free'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    code = None
    for i in range(30):
        line = cli_proc.stdout.readline()
        if not line: break
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', line.strip())
        if 'Code:' in stripped:
            code = stripped.split('Code:')[1].strip()
            break
        time.sleep(1)
    
    if not code:
        print("[!] No code"); proc.kill(); cli_proc.kill(); return
    
    print(f"[*] Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:9333', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(8.0)
        
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
        
        # Continue
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(10.0)
        
        # Fill email
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.fill(EMAIL)
            inp.press('Enter')
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(12.0)
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email: {body[:200]}")
        
        if 'enter your name' in body:
            print("[*] On name page - fresh browser...")
            for name in ['John Smith', 'Test User', 'AWS User']:
                try:
                    inp = page.locator('input:not([type="password"]):visible').first
                    inp.click()
                    inp.type(name, delay=100)
                    time.sleep(1.0)
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
                    print(f"  [!] '{name}': {e}")
            
            body = page.evaluate("document.body.innerText").lower()
            if 'enter your name' in body:
                print("[!] Still on name page in fresh browser")
                page.close(); proc.kill(); cli_proc.kill(); return
        
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
    
    # Kill fresh Chrome
    proc.kill()
    proc.wait()
    
    # Check kiro-cli
    cli_proc.wait(timeout=60)
    print(f"[*] kiro-cli exit: {cli_proc.returncode}")

if __name__ == '__main__':
    main()
