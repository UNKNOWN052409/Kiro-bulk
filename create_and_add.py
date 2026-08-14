"""
Production script: Create Kiro AI accounts and add them to 9Router panel.

This script:
1. Creates Kiro AI accounts with @havenhaus.in domain
2. Adds each account to the 9Router panel using the UI device auth flow
3. Saves results to a CSV file

Usage:
    python3 create_and_add.py [--count N] [--start N]
"""

import sys, os, time, random, string, csv, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from playwright.sync_api import sync_playwright
from panel_add_ui import panel_add_account_ui, PANEL_URL, PANEL_PASS

# Configuration
GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'
DOMAIN = 'havenhaus.in'
RESULTS_FILE = '/home/ubuntu/kiro-gen/accounts.csv'

# Existing account already added
EXISTING_ACCOUNTS = [
    ('nicholas204@havenhaus.in', 'wbh$b999%%EbC-'),
]

# Name variations for accounts
FIRST_NAMES = ['nicholas', 'andrew', 'matthew', 'anthony', 'joshua', 'daniel',
               'james', 'david', 'joseph', 'thomas', 'christopher', 'charles',
               'ryan', 'benjamin', 'samuel', 'tyler', 'brandon', 'kyle',
               'austin', 'jordan', 'nathan', 'zachary', 'aaron', 'eric',
               'kevin', 'brian', 'justin', 'adrian', 'evan', 'connor',
               'logan', 'derek', 'mitchell', 'seth', 'blake', 'cody',
               'grant', 'tristan', 'colin', 'dylan', 'ethan', 'caleb',
               'mason', 'liam', 'noah', 'oliver', 'elijah', 'lucas',
               'aiden', 'jackson']

LAST_NAMES = ['smith', 'johnson', 'williams', 'brown', 'jones', 'garcia',
              'miller', 'davis', 'rodriguez', 'martinez', 'hernandez', 'lopez',
              'gonzalez', 'wilson', 'anderson', 'thomas', 'taylor', 'moore',
              'jackson', 'martin', 'lee', 'perez', 'thompson', 'white',
              'harris', 'sanchez', 'clark', 'ramirez', 'lewis', 'robinson']


def generate_password(length=14):
    """Generate a random strong password."""
    chars = string.ascii_letters + string.digits + '!@#$%&*'
    password = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice('!@#$%&*'),
    ]
    password += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(password)
    return ''.join(password)


def create_kiro_account(browser_context, email, password):
    """Create a Kiro AI account using the AWS Builder ID flow.
    
    This is a simplified version - the full creation is in run_bot_patched.py.
    For now, we'll use the panel_add_ui flow which handles everything.
    
    Returns True if account was created and added to panel.
    """
    page = browser_context.new_page()
    page.set_default_timeout(60000)
    
    try:
        # Use the panel_add_ui function which handles the full flow
        result = panel_add_account_ui(page, email, password)
        page.close()
        return result
    except Exception as e:
        print(f"  [!] Error: {e}")
        try:
            page.close()
        except:
            pass
        return False


def load_existing_accounts():
    """Load existing accounts from CSV."""
    accounts = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                accounts.append((row['email'], row['password']))
    return accounts


def save_account(email, password, status, panel_count=-1):
    """Save account to CSV."""
    file_exists = os.path.exists(RESULTS_FILE)
    with open(RESULTS_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['email', 'password', 'status', 'panel_count', 'timestamp'])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'email': email,
            'password': password,
            'status': status,
            'panel_count': panel_count,
            'timestamp': datetime.now().isoformat()
        })


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=29, help='Number of accounts to create')
    parser.add_argument('--start', type=int, default=0, help='Starting index')
    parser.add_argument('--parallel', type=int, default=1, help='Number of parallel browsers')
    args = parser.parse_args()
    
    total_accounts = args.count
    start_idx = args.start
    
    # Load existing
    existing = load_existing_accounts()
    existing_emails = {e for e, p in existing}
    existing.update(EXISTING_ACCOUNTS)
    existing_emails.update(e for e, p in EXISTING_ACCOUNTS)
    
    print(f"[+] Existing accounts: {len(existing)}")
    print(f"[+] Need to create: {total_accounts}")
    print(f"[+] Results file: {RESULTS_FILE}")
    
    with sync_playwright() as p:
        success_count = 0
        fail_count = 0
        
        for i in range(start_idx, start_idx + total_accounts):
            # Generate account
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            last = LAST_NAMES[i % len(LAST_NAMES)]
            num = random.randint(100, 999)
            email = f"{first}{num}@{DOMAIN}"
            password = generate_password()
            
            # Ensure unique email
            while email in existing_emails:
                num = random.randint(100, 999)
                email = f"{first}{num}@{DOMAIN}"
            
            print(f"\n{'='*60}")
            print(f"[+] Account {i+1}/{start_idx + total_accounts}: {email}")
            print(f"{'='*60}")
            
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )
            page = context.new_page()
            page.set_default_timeout(60000)
            
            # Add to panel using UI device auth flow
            result = panel_add_account_ui(page, email, password)
            
            if result:
                success_count += 1
                existing_emails.add(email)
                existing.append((email, password))
                print(f"  ✅ SUCCESS: {email}")
                save_account(email, password, 'success')
            else:
                fail_count += 1
                print(f"  ❌ FAILED: {email}")
                save_account(email, password, 'failed')
            
            page.close()
            try:
                context.close()
            except:
                pass
            try:
                browser.close()
            except:
                pass
            
            # Save state
            print(f"\n[+] Progress: {success_count} success, {fail_count} failed")
            
            # Random delay between accounts to avoid rate limiting
            delay = random.uniform(10, 30)
            print(f"  [*] Waiting {delay:.1f}s before next account...")
            time.sleep(delay)
    
    print(f"\n{'='*60}")
    print(f"[+] DONE: {success_count} success, {fail_count} failed out of {total_accounts}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
