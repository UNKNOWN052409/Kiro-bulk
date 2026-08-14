"""
Debug with fresh context and proper email clearing.
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

EMAIL = 'kirotest2026@gmail.com'

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
        # Create a fresh incognito context to avoid cached values
        context = browser.new_context()
        page = context.new_page()
        
        page.goto(f'https://view.awsapps.com/start/#/device?user_code={code}', 
                  wait_until='domcontentloaded', timeout=30000)
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
            time.sleep(5.0)
        
        # Continue
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(10.0)
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After Continue: {body[:200]}")
        
        # Handle cookies again
        if 'cookie' in body:
            try:
                page.locator('button:has-text("Decline")').first.click(timeout=3000)
            except Exception:
                try:
                    page.locator('button:has-text("Accept")').first.click(timeout=3000)
                except Exception:
                    pass
            time.sleep(5.0)
        
        # Fill email - click, clear, fill
        inp = page.locator('input:not([type="password"]):visible').first
        inp.click()
        time.sleep(1.0)
        # Clear with Ctrl+A + Backspace
        inp.press('Control+a')
        time.sleep(0.5)
        inp.press('Backspace')
        time.sleep(0.5)
        # Verify cleared
        val = inp.input_value()
        print(f"[*] Input value after clear: '{val}'")
        # Fill new email
        inp.fill(EMAIL)
        time.sleep(0.5)
        val = inp.input_value()
        print(f"[*] Input value after fill: '{val}'")
        inp.press('Enter')
        time.sleep(15.0)
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email (15s): {body[:300]}")
        
        page.close()
        context.close()
    proc.kill()

if __name__ == '__main__':
    main()
