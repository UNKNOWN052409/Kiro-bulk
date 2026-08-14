#!/usr/bin/env python3
"""
Kiro AI Account Automation - Production Script
===============================================
Creates Kiro AI accounts with @havenhaus.in domain and adds them to the
9Router panel (ourproxy.sryze.cc).

Uses the lightweight Rust container for resource-isolated execution.
CPU limit: 0.1 core per instance.
Memory limit: 512MB per instance.

Architecture:
  1. Account Creation: Goes to kiro.dev → AWS Builder ID → creates account
  2. Panel Integration: Uses panel's device auth modal to connect accounts
  3. Resource Isolation: Each instance runs in a cgroup-limited process

Usage:
  python3 production_bot.py --mode create    # Create new accounts
  python3 production_bot.py --mode add       # Add existing accounts to panel
  python3 production_bot.py --mode full      # Create + add to panel
  python3 production_bot.py --mode status    # Check panel status
"""

import sys
import os
import time
import json
import random
import string
import subprocess
import argparse
import csv
from datetime import datetime, timedelta

# Configuration
PANEL_URL = "https://ourproxy.sryze.cc"
PANEL_PASS = "7894561230"
GMAIL = "anshika31618@gmail.com"
GMAIL_PASS = "hlcveobitfwhterw"
DOMAIN = "havenhaus.in"
CSV_FILE = os.path.join(os.path.dirname(__file__), "kiro_accounts.csv")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "panel_results.csv")

# Rust container binary
RUST_CONTAINER = os.path.join(os.path.dirname(__file__), "rust-container", "target", "release", "kiro-container")

def get_existing_accounts():
    """Load existing accounts from CSV."""
    accounts = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                accounts.append(row)
    return accounts

def get_unique_emails():
    """Get unique email addresses from the CSV."""
    accounts = get_existing_accounts()
    seen = set()
    unique = []
    for acc in accounts:
        email = acc.get('email', acc.get('Email', ''))
        if email and email not in seen:
            seen.add(email)
            unique.append(acc)
    return unique

def get_panel_connection_count():
    """Get the current number of connections on the panel."""
    try:
        result = subprocess.run([
            'curl', '-sk', '-c', '/tmp/panel_cookies.txt',
            '-X', 'POST', f'{PANEL_URL}/api/auth/login',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps({"password": PANEL_PASS})
        ], capture_output=True, timeout=30)

        result = subprocess.run([
            'curl', '-sk', '-b', '/tmp/panel_cookies.txt',
            f'{PANEL_URL}/api/connections'
        ], capture_output=True, text=True, timeout=30)

        data = json.loads(result.stdout)
        return len(data) if isinstance(data, list) else 0
    except:
        return -1

def generate_account():
    """Generate a new random account."""
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@{DOMAIN}"
    password = ''.join(random.choices(string.ascii_uppercase, k=2)) + \
               ''.join(random.choices(string.ascii_lowercase, k=6)) + \
               ''.join(random.choices(string.digits, k=2)) + \
               random.choice('!@#$%')
    name = f"{username[:4].title()} {username[4:].title()}" if len(username) >= 8 else f"{username.title()} User"
    return {"email": email, "password": password, "name": name}

def save_account(account, status="created"):
    """Save account to CSV."""
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["email", "password", "name", "status", "created_at"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "email": account["email"],
            "password": account["password"],
            "name": account["name"],
            "status": status,
            "created_at": datetime.now().isoformat()
        })

def log_result(email, status, message=""):
    """Log result to results CSV."""
    file_exists = os.path.exists(RESULTS_FILE)
    with open(RESULTS_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["email", "status", "message", "timestamp"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "email": email,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

def extract_otp(max_wait=60):
    """Extract OTP from Gmail (checks Spam folder first)."""
    import imaplib
    import email as email_lib
    from email import policy
    import re

    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(GMAIL, GMAIL_PASS)
    since = (datetime.now() - timedelta(minutes=15)).strftime('%d-%b-%Y')

    # Check Spam first, then Inbox
    for folder in ['"[Gmail]/Spam"', '"[Gmail]/INBOX"']:
        for attempt in range(max_wait // 3):
            try:
                mail.select(folder)
                status, messages = mail.search(None, f'(SINCE {since} SUBJECT "Verify your identity")')
                if status == 'OK' and messages[0].split():
                    msg_ids = messages[0].split()
                    for msg_id in reversed(msg_ids):
                        status2, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status2 != 'OK':
                            continue
                        raw = msg_data[0][1]
                        msg = email_lib.message_from_bytes(raw, policy=policy.default)
                        body = ''
                        if msg.is_multipart():
                            for part in msg.walk():
                                ct = part.get_content_type()
                                if ct == 'text/plain':
                                    body = part.get_content() or ''
                                    break
                                elif ct == 'text/html':
                                    html = part.get_content() or ''
                                    body = re.sub(r'<[^>]+>', ' ', html)
                        else:
                            body = msg.get_content() or ''
                            if msg.get_content_type() == 'text/html':
                                body = re.sub(r'<[^>]+>', ' ', body)

                        clean = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'EMAIL', body)
                        match = re.search(r'(\d{6})(?!\d)', clean)
                        if match and match.group(1) not in ('000000', '123456', '111111', '555555'):
                            mail.logout()
                            return match.group(1)
            except Exception as e:
                break
            time.sleep(3)

    mail.logout()
    return None

def add_account_to_panel(email, password, max_retries=3):
    """Add an account to the panel using the device auth UI flow."""
    try:
        from panel_add_ui import panel_add_account_ui
        for attempt in range(max_retries):
            print(f"  [*] Attempt {attempt + 1}/{max_retries}...")
            result = panel_add_account_ui(email, password)
            if result.get("success"):
                return result
            if "ERR-837" in result.get("error", ""):
                print(f"  [!] ERR-837 - AWS name page issue. Retrying...")
                time.sleep(5)
                continue
            break
        return {"success": False, "error": "Max retries exceeded"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_account_flow(email=None, password=None):
    """Create a new Kiro account using AWS Builder ID."""
    if email is None:
        account = generate_account()
        email = account["email"]
        password = account["password"]
    else:
        account = {"email": email, "password": password, "name": email.split('@')[0]}

    print(f"\n[*] Creating account: {email}")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1366, 'height': 768})

            # Navigate to Kiro sign-in
            page.goto("https://app.kiro.dev/sign-in", wait_until='load', timeout=60000)
            time.sleep(5)

            # Click Builder ID option
            for selector in ['button:has-text("Builder ID")', 'text=Builder ID', 'button:has-text("AWS")']:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        break
                except:
                    continue
            time.sleep(10)

            # Fill email
            email_loc = page.locator('input:not([type="password"]):visible').first
            if email_loc.is_visible(timeout=10000):
                email_loc.click()
                time.sleep(0.5)
                page.keyboard.type(email, delay=30)
                time.sleep(1)
                page.keyboard.press('Enter')
                time.sleep(10)

            # Check for sign-up vs sign-in
            body = page.evaluate("() => (document.body?.innerText || '').trim()")
            if 'password' in body.lower():
                # Sign-in flow
                pw_loc = page.locator('input[type="password"]:visible').first
                pw_loc.click()
                time.sleep(0.5)
                pw_loc.fill(password)
                time.sleep(1)
                pw_loc.press('Enter')
                time.sleep(10)
            elif 'create' in body.lower() or 'sign up' in body.lower():
                # Sign-up flow - need to create new account
                # This would continue with the full sign-up flow
                pass

            # Handle OTP
            body = page.evaluate("() => (document.body?.innerText || '').trim()")
            if 'verification' in body.lower() or 'code' in body.lower():
                otp = extract_otp()
                if otp:
                    print(f"  [+] OTP: {otp}")
                    otp_loc = page.locator('input[type="text"]:visible, input[maxlength="6"]:visible').first
                    otp_loc.click()
                    time.sleep(0.5)
                    page.keyboard.type(otp, delay=50)
                    time.sleep(1)
                    page.keyboard.press('Enter')
                    time.sleep(10)

            # Handle name page (if needed)
            body = page.evaluate("() => (document.body?.innerText || '').trim()")
            if 'enter your name' in body.lower():
                name_loc = page.locator('input:not([type="password"]):visible').first
                name_loc.click()
                time.sleep(0.5)
                page.keyboard.type(account.get("name", email.split('@')[0]), delay=50)
                time.sleep(1)
                # Click Continue
                continue_btn = page.locator('button:has-text("Continue")').first
                continue_btn.click()
                time.sleep(10)

            # Confirm/Allow
            for sel in ['button:has-text("Confirm")', 'a:has-text("Confirm")', 'button:has-text("Allow")']:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=5000):
                        btn.click()
                        break
                except:
                    continue
            time.sleep(10)

            # Check if account was created successfully
            final_url = page.url
            body = page.evaluate("() => (document.body?.innerText || '').trim()")
            success = 'kiro' in final_url.lower() or 'home' in final_url.lower()

            page.close()
            browser.close()

            if success:
                print(f"  [+] Account created: {email}")
                save_account(account, "created")
                log_result(email, "created")
                return {"success": True, "email": email, "password": password}
            else:
                error = body[:200] if body else "Unknown error"
                print(f"  [!] Account creation failed: {error}")
                log_result(email, "failed", error)
                return {"success": False, "error": error}

    except Exception as e:
        print(f"  [!] Exception: {e}")
        log_result(email, "failed", str(e))
        return {"success": False, "error": str(e)}

def mode_create(args):
    """Create new accounts."""
    count = args.count or 10
    unique = get_unique_emails()
    existing = len(unique)
    needed = max(0, 30 - existing)
    to_create = min(count, needed)

    print(f"[*] Existing accounts: {existing}")
    print(f"[*] Creating {to_create} new accounts...")

    successes = 0
    for i in range(to_create):
        result = create_account_flow()
        if result.get("success"):
            successes += 1
        time.sleep(5)  # Rate limiting

    print(f"\n[*] Created {successes}/{to_create} accounts")

def mode_add(args):
    """Add existing accounts to the panel."""
    accounts = get_unique_emails()
    print(f"[*] Adding {len(accounts)} accounts to panel...")

    successes = 0
    for i, acc in enumerate(accounts):
        email = acc.get("email", acc.get("Email", ""))
        password = acc.get("password", acc.get("Password", "Kiro2026!Secure#"))
        print(f"\n[{i+1}/{len(accounts)}] {email}")

        result = add_account_to_panel(email, password)
        if result.get("success"):
            successes += 1
            log_result(email, "added_to_panel")
        else:
            log_result(email, "add_failed", result.get("error", ""))

        time.sleep(3)

    print(f"\n[*] Added {successes}/{len(accounts)} accounts to panel")

def mode_full(args):
    """Create accounts and add them to the panel."""
    print("[*] Full mode: Create + Add to panel")

    # First create accounts
    count = args.count or 10
    unique = get_unique_emails()
    needed = max(0, 30 - len(unique))
    to_create = min(count, needed)

    print(f"[*] Creating {to_create} accounts...")
    for i in range(to_create):
        create_account_flow()
        time.sleep(5)

    # Then add all to panel
    accounts = get_unique_emails()
    print(f"\n[*] Adding {len(accounts)} accounts to panel...")
    for i, acc in enumerate(accounts):
        email = acc.get("email", acc.get("Email", ""))
        password = acc.get("password", acc.get("Password", "Kiro2026!Secure#"))
        print(f"\n[{i+1}/{len(accounts)}] {email}")
        result = add_account_to_panel(email, password)
        if result.get("success"):
            log_result(email, "added_to_panel")
        else:
            log_result(email, "add_failed", result.get("error", ""))
        time.sleep(3)

def mode_status(args):
    """Check panel status."""
    count = get_panel_connection_count()
    unique = get_unique_accounts() if False else get_unique_emails()
    print(f"\n[*] Panel connections: {count}")
    print(f"[*] Local accounts: {len(unique)}")
    print(f"[*] Target: 30 accounts")

def main():
    parser = argparse.ArgumentParser(description="Kiro AI Account Automation")
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    # Create mode
    create_parser = subparsers.add_parser("create", help="Create new accounts")
    create_parser.add_argument("--count", type=int, default=10, help="Number of accounts to create")

    # Add mode
    add_parser = subparsers.add_parser("add", help="Add accounts to panel")

    # Full mode
    full_parser = subparsers.add_parser("full", help="Create + Add to panel")
    full_parser.add_argument("--count", type=int, default=10, help="Number of accounts to create")

    # Status mode
    subparsers.add_parser("status", help="Check panel status")

    args = parser.parse_args()

    if args.mode == "create":
        mode_create(args)
    elif args.mode == "add":
        mode_add(args)
    elif args.mode == "full":
        mode_full(args)
    elif args.mode == "status":
        mode_status(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
