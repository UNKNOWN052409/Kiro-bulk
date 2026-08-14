"""
Add all existing Kiro accounts to the 9Router panel using the UI device auth flow.
"""

import sys, os, time, csv
from playwright.sync_api import sync_playwright
from panel_add_ui import panel_add_account_ui, PANEL_URL

ACCOUNTS_FILE = '/home/ubuntu/kiro-gen/kiro_accounts.csv'
RESULTS_FILE = '/home/ubuntu/kiro-gen/panel_results.csv'

def load_accounts():
    """Load unique accounts from CSV."""
    seen = set()
    accounts = []
    with open(ACCOUNTS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row['Email']
            if email in seen:
                continue
            seen.add(email)
            # Skip duplicates marked in Name
            if '(panel-login-fail)' in row['Name']:
                continue
            accounts.append({
                'name': row['Name'].replace(' (panel-pending)', '').replace(' (panel-login-fail)', ''),
                'email': email,
                'password': row['Password'],
            })
    return accounts

def main():
    accounts = load_accounts()
    print(f"[+] Found {len(accounts)} unique accounts")
    
    # nicholas204 already added, skip it
    accounts = [a for a in accounts if a['email'] != 'nicholas204@havenhaus.in']
    print(f"[+] After skipping already-added: {len(accounts)} accounts to add")
    
    results = []
    
    with sync_playwright() as p:
        for i, acc in enumerate(accounts):
            print(f"\n{'='*60}")
            print(f"[+] Adding account {i+1}/{len(accounts)}: {acc['email']}")
            print(f"{'='*60}")
            
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1366, 'height': 768},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                )
                page = context.new_page()
                page.set_default_timeout(60000)
                
                result = panel_add_account_ui(page, acc['email'], acc['password'])
                
                results.append({
                    'name': acc['name'],
                    'email': acc['email'],
                    'password': acc['password'],
                    'panel_added': 'YES' if result else 'NO',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                })
                
                page.close()
                context.close()
                browser.close()
                
                status = '✅ SUCCESS' if result else '❌ FAILED'
                print(f"\n[{status}] {acc['email']}")
                
            except Exception as e:
                print(f"[!] Exception: {e}")
                results.append({
                    'name': acc['name'],
                    'email': acc['email'],
                    'password': acc['password'],
                    'panel_added': 'ERROR',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                })
            
            # Save progress
            with open(RESULTS_FILE, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'email', 'password', 'panel_added', 'timestamp'])
                if i == 0:
                    writer.writeheader()
                writer.writerow(results[-1])
            
            # Delay between accounts
            delay = 15 + i * 5
            print(f"  [*] Waiting {delay}s...")
            time.sleep(delay)
    
    # Summary
    success = sum(1 for r in results if r['panel_added'] == 'YES')
    print(f"\n{'='*60}")
    print(f"[+] DONE: {success}/{len(accounts)} accounts added to panel")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
