#!/usr/bin/env python3
"""
AWS Builder ID Browser Authentication
=====================================
Handles the browser-based login for AWS Builder ID device auth flow.
Supports the two-step flow: Password → OTP verification code.
Reads device auth info from /tmp/kiro_device_auth.json,
automates the sign-in flow, and extracts the OTP from Gmail.

Usage:
  python3 cli_browser_auth.py [--password PASSWORD]
"""
import sys
import os
import time
import json
import imaplib
import email
import re
import argparse
import csv
from datetime import datetime

# Gmail configuration
GMAIL = "anshika31618@gmail.com"
GMAIL_PASS = "hlcveobitfwhterw"

# Playwright
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip3 install playwright && playwright install chromium")
    sys.exit(1)

def get_otp_from_gmail(timeout=120, after_timestamp=None):
    """Extract OTP from Gmail Spam or Inbox folder."""
    start_time = time.time()
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL, GMAIL_PASS)
        
        while time.time() - start_time < timeout:
            for folder in ['[Gmail]/Spam', 'INBOX']:
                mail.select(f'"{folder}"')
                status, messages = mail.search(None, 'ALL')
                
                if status == 'OK' and messages[0]:
                    msg_ids = messages[0].split()
                    for msg_id in reversed(msg_ids[-20:]):
                        status2, date_data = mail.fetch(msg_id, '(INTERNALDATE)')
                        if status2 != 'OK':
                            continue
                        
                        date_str = date_data[0].decode('utf-8', errors='ignore')
                        date_match = re.search(r'"(\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2})', date_str)
                        if date_match:
                            email_dt = datetime.strptime(date_match.group(1), '%d-%b-%Y %H:%M:%S')
                            if after_timestamp and email_dt.timestamp() < after_timestamp:
                                continue
                            if time.time() - email_dt.timestamp() > 300:
                                continue
                        
                        status3, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status3 != 'OK':
                            continue
                        
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        from_addr = msg.get('From', '')
                        
                        if 'login.awsapps.com' in from_addr or 'amazonaws.com' in from_addr:
                            html_body = ''
                            text_body = ''
                            if msg.is_multipart():
                                for part in msg.walk():
                                    ct = part.get_content_type()
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        decoded = payload.decode('utf-8', errors='ignore')
                                        if ct == 'text/html':
                                            html_body = decoded
                                        elif ct == 'text/plain':
                                            text_body = decoded
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    decoded = payload.decode('utf-8', errors='ignore')
                                    if msg.get_content_type() == 'text/html':
                                        html_body = decoded
                                    else:
                                        text_body = decoded
                            
                            # Look for 6-digit code in HTML
                            code_match = re.search(r'class="code"[^>]*>(\d{6})<', html_body)
                            if code_match and code_match.group(1) != '555555':
                                mail.logout()
                                return code_match.group(1)
                            
                            code_match = re.search(r'verification code[^>]*>(\d{6})', html_body, re.IGNORECASE)
                            if code_match and code_match.group(1) != '555555':
                                mail.logout()
                                return code_match.group(1)
                            
                            otp_match = re.search(r'\b(\d{6})\b', text_body)
                            if otp_match and otp_match.group(1) != '555555':
                                mail.logout()
                                return otp_match.group(1)
            
            time.sleep(3)
        
        mail.logout()
    except Exception as e:
        print(f"  Gmail error: {e}")
    
    return None

def get_account_password(email_addr, csv_file=None):
    """Get the password for an account from the CSV file."""
    if csv_file is None:
        csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiro_accounts.csv')
    
    if not os.path.exists(csv_file):
        return None
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_email = row.get('Email', row.get('email', ''))
            if row_email == email_addr:
                return row.get('Password', row.get('password', ''))
    return None

def dismiss_cookie_banner(page):
    """Dismiss the AWS cookie banner if present."""
    try:
        accept_btn = page.locator('[data-id="awsccc-cb-btn-accept"]')
        if accept_btn.is_visible(timeout=3000):
            accept_btn.click()
            time.sleep(1)
            print("    Cookie banner dismissed")
    except:
        pass

def automate_aws_login(playwright, device_auth_info, password=None):
    """Automate the AWS Builder ID login flow (two-step: password → OTP)."""
    email_addr = device_auth_info['email']
    verification_uri = device_auth_info['verification_uri']
    
    if password is None:
        password = get_account_password(email_addr)
    
    print(f"[*] Opening browser for AWS login...")
    print(f"    Email: {email_addr}")
    print(f"    Password: {'*' * len(password) if password else 'NOT AVAILABLE'}")
    print(f"    URI: {verification_uri}")
    
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = context.new_page()
    
    try:
        # ===== STEP 1: Open verification URI =====
        print("[*] Step 1: Opening verification URI...")
        page.goto(verification_uri, wait_until='networkidle', timeout=30000)
        time.sleep(3)
        dismiss_cookie_banner(page)
        print(f"    Current URL: {page.url}")
        
        # ===== STEP 2: Enter email =====
        print("[*] Step 2: Entering email...")
        email_input = page.locator('input[id="resolver_input_field"], input[name="username"], input[type="email"]').first
        email_input.wait_for(timeout=15000)
        email_input.fill(email_addr)
        time.sleep(1)
        
        email_submit_time = time.time()
        
        next_btn = page.locator('[data-testid="test-primary-button"]').first
        next_btn.wait_for(timeout=10000)
        next_btn.click()
        time.sleep(4)
        
        # ===== STEP 3: Enter password =====
        page_content = page.content()
        
        if 'Enter password' in page_content:
            print("[*] Step 3: Password page - entering password...")
            
            if not password:
                print("[-] No password available!")
                page.screenshot(path='/tmp/kiro_no_password.png')
                return False
            
            password_input = page.locator('input[type="password"]').first
            password_input.wait_for(timeout=10000)
            password_input.fill(password)
            time.sleep(1)
            
            continue_btn = page.locator('button:has-text("Continue")').first
            continue_btn.click()
            time.sleep(5)
            print("[+] Password submitted")
        else:
            print("[-] Password page not detected!")
            page.screenshot(path='/tmp/kiro_no_password_page.png')
            return False
        
        # ===== STEP 4: OTP verification =====
        page_content = page.content()
        
        if 'Verify your identity' in page_content or 'Verification code' in page_content:
            print("[*] Step 4: OTP verification page detected - waiting for email...")
            otp = get_otp_from_gmail(timeout=120, after_timestamp=email_submit_time)
            
            if otp:
                print(f"    Found OTP: {otp}")
                
                # Find the 6-digit OTP input
                otp_input = page.locator('input[placeholder="6-digit"], input[placeholder="Enter code"], input[name="code"], input[id="code"]').first
                
                try:
                    otp_input.wait_for(timeout=10000)
                    otp_input.fill(otp)
                    time.sleep(1)
                    
                    # Click Continue
                    continue_btn = page.locator('button:has-text("Continue")').first
                    continue_btn.click()
                    time.sleep(5)
                    print("[+] OTP submitted successfully")
                except Exception as e:
                    print(f"    Error with OTP input: {e}")
                    # Try alternative approach
                    try:
                        page.keyboard.type(otp)
                        time.sleep(1)
                        page.keyboard.press('Enter')
                        time.sleep(5)
                        print("[+] OTP typed via keyboard")
                    except Exception as e2:
                        print(f"    Keyboard approach also failed: {e2}")
                        page.screenshot(path='/tmp/kiro_otp_submit_error.png')
                        return False
            else:
                print("[-] Could not find OTP in Gmail")
                page.screenshot(path='/tmp/kiro_otp_not_found.png')
                return False
        else:
            # No OTP page - maybe it went straight to success or name setup
            print(f"    No OTP page detected. Content check: {'Verify' in page_content}")
        
        # ===== STEP 5: Handle Authorization Confirmation page =====
        time.sleep(3)
        page_content = page.content()
        
        if 'Authorization requested' in page_content or 'Confirm and continue' in page_content:
            print("[*] Step 5: Authorization confirmation page detected...")
            try:
                # Verify the code on the page matches our device code
                displayed_code = device_auth_info['user_code']
                if displayed_code in page_content:
                    print(f"    Code matches: {displayed_code}")
                
                # Click "Confirm and continue"
                confirm_btn = page.locator('button:has-text("Confirm and continue")').first
                confirm_btn.wait_for(timeout=10000)
                confirm_btn.click()
                time.sleep(5)
                print("    Authorization confirmed!")
            except Exception as e:
                print(f"    Error on confirmation page: {e}")
                page.screenshot(path='/tmp/kiro_confirm_error.png')
        
        # ===== STEP 6: Handle name setup if present =====
        page_content = page.content()
        
        if ('first name' in page_content.lower() or 'last name' in page_content.lower()) and 'Create profile' in page_content:
            print("[*] Step 6: Name setup page detected...")
            try:
                first_name_input = page.locator('input[id="firstName"], input[name="firstName"]').first
                last_name_input = page.locator('input[id="lastName"], input[name="lastName"]').first
                
                username = email_addr.split('@')[0]
                first_name = username[:4].title()
                last_name = username[4:].title() if len(username) > 4 else "User"
                
                first_name_input.fill(first_name)
                last_name_input.fill(last_name)
                time.sleep(1)
                
                submit_btn = page.locator('[data-testid="test-primary-button"], button:has-text("Create profile")').first
                submit_btn.click()
                time.sleep(5)
                print("    Name submitted")
            except Exception as e:
                print(f"    Error on name page: {e}")
                page.screenshot(path='/tmp/kiro_name_error.png')
        
        # ===== STEP 7: Check final state =====
        time.sleep(3)
        final_url = page.url
        print(f"    Final URL: {final_url}")
        
        # If we're on the verification URI or a success page, the device flow is complete
        if 'view.awsapps.com' in final_url or 'success' in final_url.lower():
            print("[+] Device auth completed successfully!")
        elif 'signin' in final_url.lower():
            print(f"    Still on sign-in page - might need to wait for redirect")
            # Wait a bit more for redirect
            time.sleep(10)
            final_url = page.url
            print(f"    After waiting: {final_url}")
        
        page.screenshot(path='/tmp/kiro_login_success.png')
        print("[+] Browser auth flow completed")
        return True
        
    except Exception as e:
        print(f"[-] Browser automation error: {e}")
        page.screenshot(path='/tmp/kiro_login_error.png')
        return False
    finally:
        browser.close()

def main():
    parser = argparse.ArgumentParser(description='AWS Builder ID browser auth for Kiro CLI')
    parser.add_argument('--password', default=None, help='Password (auto from CSV if not provided)')
    args = parser.parse_args()
    
    auth_file = '/tmp/kiro_device_auth.json'
    if not os.path.exists(auth_file):
        print(f"ERROR: Device auth file not found: {auth_file}")
        return 1
    
    with open(auth_file) as f:
        device_auth_info = json.load(f)
    
    print(f"[*] Device auth info loaded for: {device_auth_info['email']}")
    
    with sync_playwright() as p:
        success = automate_aws_login(p, device_auth_info, password=args.password)
    
    if success:
        print("[+] Browser auth completed. Token should be captured by the polling process.")
        return 0
    else:
        print("[-] Browser auth failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
