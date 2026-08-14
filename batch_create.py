#!/usr/bin/env python3
"""Batch account creation - creates multiple accounts and saves tokens locally."""
import sys, os, time, json, random, string
from datetime import datetime

# Import from final_flow
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def generate_email(prefix="kiro"):
    """Generate a random email address."""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{suffix}@havenhaus.in"

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    results_file = "created_accounts.json"
    
    # Load existing results
    results = []
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                results = json.load(f)
        except:
            results = []
    
    print(f"[*] Creating {count} accounts (已有 {len(results)} accounts)")
    
    for i in range(count):
        email = generate_email()
        print(f"\n{'='*50}")
        print(f"[*] Account {i+1}/{count}: {email}")
        print(f"{'='*50}")
        
        # Run the flow
        from final_flow import main as flow_main
        try:
            success = flow_main(email)
            if success:
                print(f"[+] Account created: {email}")
                # The token should be in the results
            else:
                print(f"[!] Account creation failed: {email}")
        except Exception as e:
            print(f"[!] Error: {e}")
        
        # Save progress
        time.sleep(5)
    
    print(f"\n[*] Done! Created {len(results)} accounts total")

if __name__ == '__main__':
    main()
