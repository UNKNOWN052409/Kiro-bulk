#!/usr/bin/env python3
"""
Batch add accounts to the panel using panel_add_ui.py module.
Tries accounts from the CSV until we reach the target count.
"""
import sys
import os
import csv
import gc
import time
import subprocess
from playwright.sync_api import sync_playwright

# Add the kiro-gen directory to path
sys.path.insert(0, os.path.dirname(__file__))

from panel_add_ui import panel_add_account_ui, PANEL_URL, PANEL_PASS

CSV_FILE = os.path.join(os.path.dirname(__file__), "kiro_accounts.csv")
TARGET_NEW_ACCOUNTS = 30
CURRENT_PANEL_COUNT = 95  # Already has 95 connections (93 existing + 2 added)


def get_accounts_to_add():
    """Get accounts that haven't been added yet (skip ones with panel-pending or already added)."""
    accounts = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('Email', '')
                password = row.get('Password', '')
                name = row.get('Name', '')
                if email and password and '(panel-login-fail)' not in name and '(panel-pending)' not in name:
                    accounts.append({'email': email, 'password': password, 'name': name})
    
    # Deduplicate by email
    seen = set()
    unique = []
    for acc in accounts:
        if acc['email'] not in seen:
            seen.add(acc['email'])
            unique.append(acc)
    
    return unique


def main():
    print("=" * 60)
    print("Kiro Account Batch Adder")
    print("=" * 60)
    print(f"Current panel count: {CURRENT_PANEL_COUNT}")
    print(f"Target: +{TARGET_NEW_ACCOUNTS} new accounts")
    print(f"Target total: {CURRENT_PANEL_COUNT + TARGET_NEW_ACCOUNTS}")
    print()
    
    accounts = get_accounts_to_add()
    print(f"Available accounts: {len(accounts)}")
    for acc in accounts[:5]:
        print(f"  - {acc['email']}")
    if len(accounts) > 5:
        print(f"  ... and {len(accounts) - 5} more")
    print()
    
    # Try adding accounts
    success_count = 0
    for i, acc in enumerate(accounts):
        if success_count >= TARGET_NEW_ACCOUNTS:
            print(f"\n[+] Reached target! Added {success_count} accounts.")
            break
        
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(accounts)}] Adding: {acc['email']}")
        print(f"{'='*60}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(
                    'http://localhost:9222',
                    timeout=120000
                )
                context = browser.contexts[0]
                page = context.new_page()
                
                result = panel_add_account_ui(
                    page,
                    kiro_email=acc['email'],
                    kiro_password=acc['password'],
                    user_name=acc['name']
                )
                
                page.close()
                context.close()
                browser.close()
                
                if result:
                    success_count += 1
                    print(f"[+] Successfully added: {acc['email']} ({success_count}/{TARGET_NEW_ACCOUNTS})")
                else:
                    print(f"[-] Failed to add: {acc['email']}")
                
        except Exception as e:
            print(f"[-] Error adding {acc['email']}: {e}")
            # Kill any orphaned browser processes
            try:
                subprocess.run(['pkill', '-f', 'headless-shell'], capture_output=True)
            except:
                pass
        
        # Force garbage collection between iterations
        gc.collect()
        
        # Wait between attempts to avoid rate limiting
        time.sleep(5)
    
    print(f"\n{'='*60}")
    print(f"Summary: Added {success_count} accounts")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
