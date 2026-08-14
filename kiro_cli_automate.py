#!/usr/bin/env python3
"""Automate the kiro-cli device auth flow using CDP browser."""
import sys
import os
import time
import re
import imaplib
import email
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail
from playwright.sync_api import sync_playwright

# AWS account to use
EMAIL = 'ax3p0kzyk6@havenhaus.in'
NAME = 'Ross Espinoza'
USER_CODE = 'PRZT-FGSK'

VERIFY_URL = f'https://view.awsapps.com/start/#/device?user_code={USER_CODE}'

def main():
    print(f"[*] Automating kiro-cli device auth for {EMAIL}")
    print(f"[*] Verification URL: {VERIFY_URL}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=60000)
        context = browser.contexts[0]
        page = context.new_page()
        
        # Step 1: Navigate to verification URL
        print("[*] Navigating to verification URL...")
        page.goto(VERIFY_URL, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # Step 2: Check current state
        current_url = page.url
        print(f"[*] Current URL: {current_url}")
        
        # Click Continue on the device verification page to start sign-in
        continue_clicked = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                if (!vis) continue;
                const t = (b.textContent || '').trim().toLowerCase();
                if (t.includes('continue')) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")
        print(f"  [+] Continue clicked on device page: {continue_clicked}")
        time.sleep(5.0)
        
        current_url = page.url
        print(f"[*] URL after Continue: {current_url}")
        
        # Check if we need to sign in
        if 'signin' in current_url or 'login' in current_url:
            print("[*] Need to sign in first...")
            
            # Fill email
            time.sleep(3.0)
            email_filled = page.evaluate(f"""() => {{
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {{
                    const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                    if (!vis) continue;
                    const type = (inp.type || '').toLowerCase();
                    if (type === 'email' || type === 'text') {{
                        inp.focus();
                        inp.value = '';
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(inp, '{EMAIL}');
                        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                }}
                return false;
            }}""")
            print(f"  [+] Email filled: {email_filled}")
            
            # Submit
            page.keyboard.press('Enter')
            time.sleep(8.0)
            
            # Step 3: Name page
            name_detected = page.evaluate("""() => (document.body?.innerText || '').toLowerCase().includes('enter your name')""")
            if name_detected:
                print("[*] Name page detected...")
                name_loc = page.locator('input:not([type="password"]):visible').first
                if name_loc.is_visible(timeout=5000):
                    name_loc.fill(NAME)
                    time.sleep(1.0)
                    continue_btn = page.locator('button:has-text("Continue")').first
                    if continue_btn.is_visible(timeout=5000):
                        continue_btn.click()
                        print("  [+] Name filled + Continue clicked")
                        time.sleep(10.0)
            
            # Step 4: OTP page
            otp_detected = page.evaluate("""() => (document.body?.innerText || '').toLowerCase().includes('verify your email')""")
            if otp_detected:
                print("[*] OTP page detected...")
                # Get fresh OTP
                otp_arrival = time.time()
                time.sleep(15.0)  # Wait for email to arrive
                otp = extract_otp_gmail(EMAIL, timeout=30, after_timestamp=otp_arrival)
                if otp:
                    print(f"  [+] OTP found: {otp}")
                    # Fill OTP
                    otp_filled = page.evaluate(f"""() => {{
                        const inputs = document.querySelectorAll('input');
                        for (const inp of inputs) {{
                            const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                            if (!vis) continue;
                            const type = (inp.type || '').toLowerCase();
                            if (type === 'text' || type === 'number' || type === '') {{
                                inp.focus();
                                inp.value = '';
                                const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                s.call(inp, '{otp}');
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                return true;
                            }}
                        }}
                        return false;
                    }}""")
                    print(f"  [+] OTP filled: {otp_filled}")
                    time.sleep(1.0)
                    page.keyboard.press('Enter')
                    time.sleep(10.0)
            
            # Step 5: Confirm page
            confirm_detected = page.evaluate("""() => {
                const body = (document.body?.innerText || '').toLowerCase();
                return body.includes('confirm') && body.includes('continue');
            }""")
            if confirm_detected:
                print("[*] Confirm page detected...")
                confirm_btn = page.locator('button:has-text("Confirm")').first
                if confirm_btn.is_visible(timeout=5000):
                    confirm_btn.click()
                    print("  [+] Confirm clicked")
                    time.sleep(10.0)
            
            # Step 6: Allow page (if it appears)
            allow_detected = page.evaluate("""() => {
                const body = (document.body?.innerText || '').toLowerCase();
                return body.includes('allow');
            }""")
            if allow_detected:
                print("[*] Allow page detected...")
                allow_btn = page.locator('button:has-text("Allow")').first
                if allow_btn.is_visible(timeout=5000):
                    allow_btn.click()
                    print("  [+] Allow clicked")
                    time.sleep(10.0)
        
        # Check final state
        time.sleep(5.0)
        final_url = page.url
        print(f"[*] Final URL: {final_url}")
        
        page_text = page.evaluate("() => document.body?.innerText || ''")
        print(f"[*] Page text: {page_text[:200]}")
        
        page.close()
    
    print("[*] Done!")

if __name__ == '__main__':
    main()
