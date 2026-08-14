#!/usr/bin/env python3
"""
Account Creator CLI - Create accounts on any website using Camoufox + Residential Proxy
Supports Kiro Builder ID and generic registration forms.
"""
import argparse
import csv
import json
import os
import random
import re
import string
import sys
import time
from datetime import datetime
from pathlib import Path

from camoufox.sync_api import Camoufox

DEFAULT_TIMEOUT_MS = 30000
PROXYRISE_API_KEY = "pgw-d890748b9e9c734c66a3c1a327fd1db84724cad6cbbe440d"
PROXYRISE_ENDPOINT = "gate.smartproxy.com:7000"
SIGN_IN_URL = "https://app.kiro.dev/signin"

CONFIG_DIR = os.path.expanduser("~/.proxy_cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


def load_settings():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            s = json.load(f)
            return s.get("api_key", PROXYRISE_API_KEY), s.get("endpoint", PROXYRISE_ENDPOINT)
    return PROXYRISE_API_KEY, PROXYRISE_ENDPOINT


def get_proxy_config(country="us"):
    api_key, endpoint = load_settings()
    return {
        'server': f'http://{endpoint}',
        'username': f'res-{country}',
        'password': api_key,
    }


def create_browser(proxy_config=None, headless=False):
    kwargs = {
        'geoip': True,
        'humanize': True,
        'headless': headless,
        'os': 'windows',
    }
    if proxy_config:
        kwargs['proxy'] = proxy_config
    return Camoufox(**kwargs)


def find_visible_selector(page, selectors, timeout_ms=15000):
    end = time.time() + timeout_ms / 1000
    while time.time() < end:
        for sel in selectors:
            visible = page.evaluate(f"""() => {{
                const el = document.querySelector({json.dumps(sel)});
                return !!(el && el.offsetWidth > 0 && el.offsetHeight > 0);
            }}""")
            if visible:
                return sel
        time.sleep(0.3)
    return None


def js_click(page, selector):
    return page.evaluate(f"""() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return false;
        el.scrollIntoView({{ block: 'center', behavior: 'instant' }});
        el.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
        el.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
        el.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
        return true;
    }}""")


def js_click_by_text(page, text, exact=False):
    if exact:
        return page.evaluate(f"""() => {{
            const all = Array.from(document.querySelectorAll('button, a, [role="button"]'));
            const target = all.find(el => el.textContent.trim() === {json.dumps(text)});
            if (!target) return false;
            target.scrollIntoView({{ block: 'center', behavior: 'instant' }});
            target.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
            target.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
            target.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
            return true;
        }}""")
    return page.evaluate(f"""() => {{
        const all = Array.from(document.querySelectorAll('button, a, [role="button"]'));
        const target = all.find(el => el.textContent.trim().toLowerCase().includes({json.dumps(text.lower())}));
        if (!target) return false;
        target.scrollIntoView({{ block: 'center', behavior: 'instant' }});
        target.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
        target.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
        target.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
        return true;
    }}""")


def js_fill(page, selector, value):
    return page.evaluate(f"""() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return false;
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeInputValueSetter.call(el, {json.dumps(value)});
        el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
        el.dispatchEvent(new Event('blur', {{ bubbles: true, cancelable: true }}));
        return true;
    }}""")


def fill_field(page, selector, value):
    js_fill(page, selector, value)
    page.wait_for_timeout(random.randint(100, 300))


def click_by_text(page, texts, timeout_ms=15000):
    for text in texts:
        if js_click_by_text(page, text):
            return True
    return False


def generate_name():
    first_names = ["James","Maria","John","Emma","Robert","Olivia","Michael","Sophia",
                   "David","Isabella","William","Mia","Richard","Charlotte","Joseph","Amelia"]
    last_names = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
                  "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def generate_email_from_name(name, domain):
    clean = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{clean}{suffix}@{domain}"


def generate_secure_password(length=16):
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-="
    pw = [random.choice(upper), random.choice(lower), random.choice(digits), random.choice(symbols)]
    all_chars = upper + lower + digits + symbols
    pw += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pw)
    return "".join(pw)


def extract_verification_code(text):
    match = re.search(r"Verification\s*code:?\s*(\d{6})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{6})\b", text)
    if match:
        return match.group(1)
    return None


def run_kiro_builder_id(page, domain, timeout_ms=DEFAULT_TIMEOUT_MS):
    name = generate_name()
    email = generate_email_from_name(name, domain)
    password = generate_secure_password()

    print(f"\n[*] Name: {name}")
    print(f"[*] Email: {email}")
    print(f"[*] Password: {password}")

    page.goto(SIGN_IN_URL)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(random.randint(2500, 4500))

    aws_found = js_click_by_text(page, "AWS Builder ID") or js_click_by_text(page, "Builder ID")
    if not aws_found:
        aws_found = page.evaluate("""() => {
            const all = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
            const target = all.find(b => b.textContent.includes('Builder ID') && !b.textContent.includes('Apple'));
            if (!target) return false;
            target.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
            target.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            return true;
        }""")
    if aws_found:
        print("[+] Clicked AWS Builder ID")
    else:
        page.screenshot(path="debug_builder_id.png")
        raise Exception("AWS Builder ID button not found")

    page.wait_for_timeout(random.randint(4000, 6000))

    if "app.kiro.dev" in page.url:
        print("[*] Still on kiro.dev, waiting for redirect...")
        page.wait_for_timeout(8000)

    if "app.kiro.dev" in page.url:
        page.goto(SIGN_IN_URL)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(5000)
        js_click_by_text(page, "Builder ID")
        page.wait_for_timeout(10000)

    if "app.kiro.dev" in page.url:
        raise Exception("Could not redirect to AWS Builder ID page")

    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(5000)

    email_present = page.evaluate("""() => {
        const el = document.querySelector('input[type="email"]');
        return !!(el && el.offsetWidth > 0);
    }""")
    if not email_present:
        raise Exception("Email input not found")

    js_fill(page, "input[type='email']", email)
    print(f"[+] Email filled: {email}")
    page.wait_for_timeout(random.randint(1000, 2000))

    js_click_by_text(page, "Continue")
    print("[+] Continue clicked (email).")
    page.wait_for_timeout(random.randint(3000, 5000))

    for _ in range(6):
        if "profile.aws.amazon.com" in page.url:
            break
        page.wait_for_timeout(3000)
        js_click_by_text(page, "Continue")
        page.wait_for_timeout(2000)

    page.wait_for_timeout(random.randint(2000, 4000))

    name_filled = False
    for _ in range(6):
        name_sel = page.evaluate("""() => {
            const all = document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([type="email"])');
            for (const el of all) {
                if (el.offsetWidth > 0 && el.offsetHeight > 0) return '#' + el.id;
            }
            return '';
        }""")
        if name_sel:
            js_fill(page, name_sel, name)
            print("[+] Name filled.")
            page.wait_for_timeout(random.randint(500, 1000))
            js_click_by_text(page, "Continue")
            print("[+] Continue clicked (name).")
            name_filled = True
            break
        ccba_present = page.evaluate("""() => {
            const radios = document.querySelectorAll('input[name="awsccc-u-rg-ccba-allowed"]');
            return radios.length > 0;
        }""")
        if ccba_present:
            print("[*] Accepting CCBA consent...")
            page.evaluate("""() => {
                const radios = document.querySelectorAll('input[name="awsccc-u-rg-ccba-allowed"]');
                for (const r of radios) {
                    if (r.nextSibling && r.nextSibling.textContent.trim().toLowerCase().includes('yes')) {
                        r.click(); return true;
                    }
                }
                if (radios.length > 0) { radios[0].click(); return true; }
                return false;
            }""")
            page.wait_for_timeout(2000)
        page.wait_for_timeout(3000)

    if not name_filled:
        print("[!] Name field not found, continuing...")
        js_click_by_text(page, "Continue")
        page.wait_for_timeout(3000)

    page.wait_for_timeout(random.randint(2000, 4000))

    print("[*] Waiting for verification email... (you need mail_reader configured)")
    print("[*] If auto-verification fails, enter code manually in the browser.")
    page.wait_for_timeout(15000)

    pw_found = False
    for _ in range(6):
        pw_present = page.evaluate("""() => {
            const el = document.querySelector('input[type="password"]');
            return !!(el && el.offsetWidth > 0);
        }""")
        if pw_present:
            js_fill(page, "input[type='password']", password)
            print("[+] Password filled.")
            page.wait_for_timeout(random.randint(500, 1000))
            js_click_by_text(page, "Continue") or js_click_by_text(page, "Create") or js_click_by_text(page, "Create AWS Builder ID")
            print("[+] Account created!")
            pw_found = True
            break
        page.wait_for_timeout(3000)

    if not pw_found:
        print("[!] Password fields not found. Please complete manually.")

    return {"name": name, "email": email, "password": password}


def ask_user_for_selectors():
    print("\n" + "=" * 60)
    print("INTERACTIVE MODE - Help me find the form fields")
    print("=" * 60)
    email_sel = input("Email field selector (e.g., #email): ").strip()
    password_sel = input("Password field selector (e.g., #password): ").strip()
    confirm_sel = input("Confirm Password selector (leave empty if none): ").strip()
    submit_sel = input("Submit button selector (e.g., button[type='submit']): ").strip()
    return {"email": email_sel, "password": password_sel, "confirm_password": confirm_sel or None, "submit": submit_sel}


def create_account_on_page(page, url, email, password, custom_selectors=None):
    page.goto(url)
    page.wait_for_timeout(3000)

    if custom_selectors:
        email_sels = [custom_selectors["email"]]
        pw_sels = [custom_selectors["password"]]
        submit_sels = [custom_selectors["submit"]]
    else:
        email_sels = [
            "input[type='email']", "input[name='email']", "input[id='email']",
            "input[placeholder*='email' i]", "input[name='username']", "input[id='username']",
        ]
        pw_sels = ["input[type='password']", "input[name='password']", "input[id='password']"]
        submit_sels = [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Sign Up'), button:has-text('Register'), button:has-text('Create')",
        ]

    print("[*] Looking for email field...")
    email_sel = None
    for sel in email_sels:
        visible = page.evaluate(f"""() => {{
            const el = document.querySelector({json.dumps(sel)});
            return !!(el && el.offsetWidth > 0 && el.offsetHeight > 0);
        }}""")
        if visible:
            email_sel = sel
            break
    if not email_sel:
        print("[!] Could not find email field automatically.")
        custom = ask_user_for_selectors()
        return create_account_on_page(page, url, email, password, custom)

    js_fill(page, email_sel, email)
    print(f"[+] Email filled: {email}")

    print("[*] Looking for password field...")
    pw_sel = find_visible_selector(page, pw_sels, 15000)
    if not pw_sel:
        print("[!] Could not find password field.")
        return False

    js_fill(page, pw_sel, password)
    print("[+] Password filled.")

    print("[*] Looking for submit button...")
    for sel in submit_sels:
        if js_click(page, sel):
            print("[+] Submit clicked.")
            page.wait_for_timeout(3000)
            return True
    print("[!] Could not find submit button.")
    return False


def save_credentials(url, email, password, status="created"):
    csv_file = Path(__file__).parent / "created_accounts.csv"
    file_exists = csv_file.exists()
    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["URL", "Email", "Password", "Status", "Timestamp"])
        writer.writerow([url, email, password, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    print(f"[+] Saved to {csv_file}")


def run_acc_creator(args):
    mode_label = "Kiro Builder ID" if args.kiro else "Generic"
    print("=" * 60)
    print(f"ACCOUNT CREATOR - {mode_label} - Camoufox + Residential Proxy")
    print("=" * 60)
    if args.kiro:
        print(f"Mode:            Kiro Builder ID (email domain: {args.email_domain})")
    else:
        print(f"Target URL:      {args.url or '(not set)'}")
    print(f"IP Rotation:     Every {args.rotate_every} minutes")
    print(f"Country:         {args.country.upper()}")
    print(f"Headless:        {'Yes' if args.headless else 'No'}")
    print(f"Delay:           {args.delay}s between runs")
    print("=" * 60)

    proxy_config = get_proxy_config(args.country)
    run_number = 0
    start_time = time.time()
    rotate_interval = args.rotate_every * 60

    try:
        while True:
            run_number += 1
            elapsed = time.time() - start_time
            remaining = rotate_interval - (elapsed % rotate_interval)

            print(f"\n{'─' * 60}")
            print(f"  RUN #{run_number}  |  IP rotates in {int(remaining)}s")
            print(f"{'─' * 60}")

            with create_browser(proxy_config, headless=args.headless) as browser:
                page = browser.new_page()
                page.set_default_timeout(30000)
                page.wait_for_timeout(random.randint(1000, 2000))

                if args.kiro:
                    result = run_kiro_builder_id(page, args.email_domain)
                    save_credentials(SIGN_IN_URL, result["email"], result["password"], "created")
                else:
                    if not args.url:
                        print("[-] URL is required in generic mode.")
                        return 1
                    email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}@{args.email_domain}"
                    password = args.password if args.password else generate_secure_password()
                    print(f"[*] Email: {email}")
                    success = create_account_on_page(page, args.url, email, password)
                    status = "submitted" if success else "failed"
                    save_credentials(args.url, email, password, status)

            if not args.repeat:
                print("\n[Done] Single run.")
                input("Press Enter to exit...")
                return 0

            time_since_start = time.time() - start_time
            if time_since_start >= rotate_interval:
                print(f"\n[*] {args.rotate_every} min elapsed → rotating IP...")
                start_time = time.time()

            print(f"\n[*] Waiting {args.delay}s before next run...")
            time.sleep(args.delay)

    except KeyboardInterrupt:
        print("\n[!] Stopped by user.")
        return 0
    except Exception as e:
        print(f"\n[-] Error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Account Creator - Camoufox + Residential Proxy + Fingerprint Rotation"
    )
    parser.add_argument("url", nargs="?", default=None, help="Registration URL (required in generic mode)")
    parser.add_argument("--kiro", "-k", action="store_true", help="Use Kiro Builder ID flow")
    parser.add_argument("--password", "-p", help="Password (auto-generated if omitted)")
    parser.add_argument("--email-domain", "-d", default="gmail.com", help="Email domain (default: gmail.com)")
    parser.add_argument("--country", "-c", default="us", help="Proxy country (default: us)")
    parser.add_argument("--rotate-every", "-r", type=int, default=5, help="Rotate IP every N minutes (default: 5)")
    parser.add_argument("--delay", type=int, default=30, help="Delay between runs in seconds (default: 30)")
    parser.add_argument("--repeat", action="store_true", help="Loop and create multiple accounts")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()
    sys.exit(run_acc_creator(args))


if __name__ == "__main__":
    raise SystemExit(main())
