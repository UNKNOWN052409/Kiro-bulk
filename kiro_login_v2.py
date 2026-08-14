#!/usr/bin/env python3
"""
Kiro CLI Token Capture v2
==========================
This approach:
1. Starts kiro-cli login WITHOUT --use-device-flow (it will open a browser)
2. Intercepts the browser that kiro-cli opens via CDP
3. Automates the AWS Builder ID login in that browser
4. The kiro-cli handles the rest and stores the token

The key difference: when kiro-cli opens the browser itself, it uses its own
OAuth flow with proper redirect handling, so the token gets stored correctly.
"""
import sys
import os
import time
import json
import argparse
import subprocess
import re
import imaplib
import email
from datetime import datetime
import threading

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

# Gmail configuration
GMAIL = "anshika31618@gmail.com"
GMAIL_PASS = "hlcveobitfwhterw"


def get_otp_from_gmail(after_timestamp, timeout=120):
    """Extract OTP from Gmail Spam or Inbox folder."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(GMAIL, GMAIL_PASS)
            
            for folder in ['[Gmail]/Spam', 'INBOX']:
                mail.select(f'"{folder}"')
                status, messages = mail.search(None, 'ALL')
                
                if status == 'OK' and messages[0]:
                    msg_ids = messages[0].split()
                    for msg_id in reversed(msg_ids[-10:]):
                        status2, date_data = mail.fetch(msg_id, '(INTERNALDATE)')
                        if status2 != 'OK':
                            continue
                        
                        date_str = date_data[0].decode('utf-8', errors='ignore')
                        date_match = re.search(r'"(\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2})', date_str)
                        if not date_match:
                            continue
                        
                        email_dt = datetime.strptime(date_match.group(1), '%d-%b-%Y %H:%M:%S')
                        if email_dt.timestamp() < after_timestamp:
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
                            if msg.is_multipart():
                                for part in msg.walk():
                                    ct = part.get_content_type()
                                    payload = part.get_payload(decode=True)
                                    if payload and ct == 'text/html':
                                        html_body = payload.decode('utf-8', errors='ignore')
                                        break
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload and msg.get_content_type() == 'text/html':
                                    html_body = payload.decode('utf-8', errors='ignore')
                            
                            code_match = re.search(r'class="code"[^>]*>(\d{6})<', html_body)
                            if code_match and code_match.group(1) != '555555':
                                mail.logout()
                                return code_match.group(1)
                            
                            code_match = re.search(r'verification code[^>]*>(\d{6})', html_body, re.IGNORECASE)
                            if code_match and code_match.group(1) != '555555':
                                mail.logout()
                                return code_match.group(1)
            
            mail.logout()
        except Exception as e:
            print(f"  Gmail error: {e}")
        
        time.sleep(3)
    
    return None


def automate_signin(page, email_addr, password):
    """Automate the AWS Builder ID sign-in flow on a given page."""
    try:
        # Dismiss cookie banner
        try:
            accept_btn = page.locator('[data-id="awsccc-cb-btn-accept"]')
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                time.sleep(1)
        except:
            pass
        
        # Enter email
        email_input = page.locator('input[id="resolver_input_field"], input[name="username"], input[type="email"]').first
        email_input.wait_for(timeout=15000)
        email_input.fill(email_addr)
        time.sleep(1)
        
        email_submit_time = time.time()
        
        next_btn = page.locator('[data-testid="test-primary-button"]').first
        next_btn.click()
        time.sleep(4)
        
        # Enter password
        password_input = page.locator('input[type="password"]').first
        password_input.wait_for(timeout=10000)
        password_input.fill(password)
        time.sleep(1)
        
        continue_btn = page.locator('button:has-text("Continue")').first
        continue_btn.click()
        time.sleep(5)
        
        # Get OTP
        otp = get_otp_from_gmail(after_timestamp=email_submit_time, timeout=120)
        
        if otp:
            otp_input = page.locator('input[placeholder="6-digit"], input[name="code"], input[id="code"]').first
            try:
                otp_input.wait_for(timeout=10000)
                otp_input.fill(otp)
                time.sleep(1)
                continue_btn = page.locator('button:has-text("Continue")').first
                continue_btn.click()
                time.sleep(5)
            except:
                page.keyboard.type(otp)
                time.sleep(1)
                page.keyboard.press('Enter')
                time.sleep(5)
        
        # Handle confirmation
        time.sleep(3)
        if 'Confirm and continue' in page.content():
            confirm_btn = page.locator('button:has-text("Confirm and continue")').first
            confirm_btn.click()
            time.sleep(5)
        
        print(f"[+] Sign-in completed. URL: {page.url}")
        return True
        
    except Exception as e:
        print(f"[-] Sign-in error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Kiro CLI login v2')
    parser.add_argument('--email', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    
    email_addr = args.email
    password = args.password
    
    print(f"[*] Starting Kiro CLI login (browser mode) for: {email_addr}")
    
    # Start kiro-cli login (without --use-device-flow, it will open a browser)
    proc = subprocess.Popen(
        ['kiro-cli', 'login', '--license', 'free'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Read output in a thread
    output_lines = []
    def read_output():
        for line in proc.stdout:
            line = line.strip()
            if line:
                output_lines.append(line)
                # Only print non-spinner lines
                if '▰' not in line and '▱' not in line:
                    print(f"  CLI: {line}")
    
    output_thread = threading.Thread(target=read_output, daemon=True)
    output_thread.start()
    
    # Wait a bit for the browser to open
    time.sleep(5)
    
    # Connect to the browser that kiro-cli opened via CDP
    print("[*] Connecting to kiro-cli's browser...")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp('http://localhost:9222')
            contexts = browser.contexts
            print(f"    Found {len(contexts)} browser context(s)")
            
            # Find the page with AWS sign-in
            target_page = None
            for ctx in contexts:
                for page in ctx.pages:
                    if 'signin' in page.url or 'awsapps' in page.url:
                        target_page = page
                        break
                if target_page:
                    break
            
            if target_page:
                print(f"    Found AWS sign-in page: {target_page.url}")
                automate_signin(target_page, email_addr, password)
            else:
                print("    No AWS sign-in page found. Pages:")
                for ctx in contexts:
                    for page in ctx.pages:
                        print(f"      - {page.url}")
                
                # Create a new page and navigate to the AWS start URL
                if contexts:
                    new_page = contexts[0].new_page()
                    new_page.goto('https://view.awsapps.com/start', wait_until='networkidle', timeout=30000)
                    time.sleep(3)
                    automate_signin(new_page, email_addr, password)
                    new_page.close()
            
        except Exception as e:
            print(f"[-] Browser connection error: {e}")
    
    # Wait for kiro-cli to complete
    print("[*] Waiting for kiro-cli to finish...")
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        print("    Timeout - killing kiro-cli")
        proc.kill()
    
    # Check output for success
    full_output = '\n'.join(output_lines)
    if 'Successfully' in full_output or 'logged in' in full_output.lower() or 'Logged in' in full_output:
        print("[+] Kiro CLI login successful!")
    else:
        print(f"[-] Kiro CLI may have failed. Return code: {proc.returncode}")
    
    # Look for stored token
    print("[*] Looking for stored token...")
    
    # Check .kiro directory
    settings_dir = os.path.expanduser('~/.kiro')
    for root, dirs, files in os.walk(settings_dir):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                with open(filepath, 'r') as fp:
                    content = fp.read()
                    if len(content) > 2 and ('token' in content.lower() or 'access' in content.lower()):
                        print(f"    Found: {filepath} ({len(content)} bytes)")
                        if args.output:
                            with open(args.output, 'w') as out:
                                out.write(content)
            except:
                pass
    
    # Check .fig directory (fig_auth might store there)
    fig_dir = os.path.expanduser('~/.fig')
    if os.path.exists(fig_dir):
        for root, dirs, files in os.walk(fig_dir):
            for f in files:
                filepath = os.path.join(root, f)
                print(f"    Fig file: {filepath}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
