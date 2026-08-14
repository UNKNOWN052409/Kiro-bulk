#!/usr/bin/env python3
"""Open Kiro sign-in, click Builder ID, fill generated email, verify, and create account.

Usage:
    python kiro_builder_id.py example.com

Uses Camoufox anti-detect browser + optional residential proxy.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import string
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from camoufox.sync_api import Camoufox

SIGN_IN_URL = "https://app.kiro.dev/signin"


def build_random_name(length: int = 10) -> str:
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for _ in range(length))


def normalize_domain(raw_domain: str) -> str:
    cleaned = raw_domain.strip().lower()
    for prefix in ["http://", "https://"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    cleaned = cleaned.strip("/")
    if not cleaned or " " in cleaned or "." not in cleaned:
        raise ValueError("Please provide a valid website domain like example.com")
    return cleaned


def safe_safe_print(*args, **kwargs):
    try:
        safe_print(*args, **kwargs)
    except OSError:
        pass


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open Kiro Builder ID sign-in, fill a random email, verify, and create account."
    )
    parser.add_argument("domain", help="Email domain, e.g. example.com")
    parser.add_argument("--proxy", help="Proxy server (e.g. http://user:pass@host:port)")
    parser.add_argument("--geoip", action="store_true", help="Auto-detect proxy IP for locale matching")
    parser.add_argument("--no-click-continue", action="store_true",
                        help="Fill email but do not click Continue.")
    parser.add_argument("--repeat", action="store_true", help="Loop automatically.")
    parser.add_argument("--immediate", action="store_true",
                        help="Loop immediately without waiting.")
    parser.add_argument("--delay", type=int, default=30,
                        help="Delay in seconds between repeat runs. Default: 30")
    parser.add_argument("--headless", action="store_true", help="Run headless.")
    return parser.parse_args()


add_automation_dir = str(Path(__file__).resolve().parent.parent)
if add_automation_dir not in sys.path:
    sys.path.append(add_automation_dir)

try:
    import mail_reader
except ImportError as err:
    safe_print(f"Warning: Could not import mail_reader: {err}")


def generate_secure_password(length: int = 16) -> str:
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    pw = [random.choice(upper), random.choice(lower), random.choice(digits), random.choice(symbols)]
    all_chars = upper + lower + digits + symbols
    pw += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pw)
    return "".join(pw)


def extract_code(text: str) -> str | None:
    match = re.search(r"Verification\s*code:?\s*(\d{6})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{6})\b", text)
    if match:
        return match.group(1)
    return None


def poll_for_verification_code(target_email: str, seen_uids: set[str], timeout_seconds: int = 120) -> tuple[str, str]:
    safe_print(f"Waiting for verification email for {target_email}...")
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            emails = mail_reader.fetch_emails(unread_only=True, limit=10, mark_as_read=False)
            for mail in emails:
                if mail["uid"] in seen_uids:
                    continue
                subject = mail["subject"]
                if "verify your aws builder id" in subject.lower() and target_email.lower() in mail["to"].lower():
                    body = mail["body_text"] or mail["body_html"] or ""
                    code = extract_code(body)
                    if code:
                        mail_reader.mark_email_read(mail["uid"])
                        return code, mail["uid"]
        except Exception as e:
            safe_print(f"Error checking emails: {e}")
        time.sleep(5)
    raise TimeoutException(f"Timed out waiting for verification email for {target_email}")


def save_credentials(email: str, password: str) -> None:
    script_dir = Path(__file__).parent
    csv_file = script_dir / "credentials.csv"
    file_exists = csv_file.exists()
    try:
        with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Email", "Password", "Timestamp"])
            writer.writerow([email, password, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        safe_print(f"Saved credentials to {csv_file}")
    except Exception as e:
        safe_print(f"Error saving credentials: {e}")


def load_names() -> list[str]:
    script_dir = Path(__file__).parent
    names_file = script_dir / "names.txt"
    if names_file.exists():
        try:
            with open(names_file, "r", encoding="utf-8") as f:
                names = [line.strip() for line in f if line.strip()]
                if names:
                    return names
        except Exception as e:
            safe_print(f"Warning: Could not read names.txt: {e}")
    return ["Maria José Silva", "John Smith", "Emma Watson", "Alex Jones"]


def run_once(args: argparse.Namespace, domain: str, run_number: int):
    names = load_names()
    selected_name = random.choice(names)
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', selected_name.lower())
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    generated_email = f"{clean_name}{random_suffix}@{domain}"

    safe_print(f"\nRun #{run_number}")
    safe_print(f"Selected Name: {selected_name}")
    safe_print(f"Generated email: {generated_email}")

    proxy_config = None
    if args.proxy:
        proxy_config = {'server': args.proxy}

    browser_kwargs = {
        'geoip': args.geoip or bool(args.proxy),
        'humanize': True,
        'headless': args.headless,
        'os': 'windows',
    }
    if proxy_config:
        browser_kwargs['proxy'] = proxy_config

    with Camoufox(**browser_kwargs) as browser:
        page = browser.new_page()
        page.set_default_timeout(30000)

        page.goto(SIGN_IN_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(random.randint(2000, 4000))

        # Click Builder ID via JS
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
            safe_print("Clicked AWS Builder ID")
        else:
            page.screenshot(path="debug_builder_id.png")
            raise Exception("AWS Builder ID button not found")

        page.wait_for_timeout(random.randint(4000, 6000))

        if "app.kiro.dev" in page.url:
            safe_print("Still on kiro.dev, waiting for redirect...")
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

        # Fill email via JS
        email_present = page.evaluate("""() => {
            const el = document.querySelector('input[type="email"]');
            return !!(el && el.offsetWidth > 0);
        }""")
        if not email_present:
            raise Exception("Email input not found")

        js_fill(page, "input[type='email']", generated_email)
        safe_print("Email filled.")

        if not args.no_click_continue:
            js_click_by_text(page, "Continue")
            safe_print("Continue clicked for email.")
            page.wait_for_timeout(random.randint(3000, 5000))

            for _ in range(6):
                if "profile.aws.amazon.com" in page.url:
                    break
                page.wait_for_timeout(3000)
                js_click_by_text(page, "Continue")
                page.wait_for_timeout(2000)

            page.wait_for_timeout(random.randint(2000, 4000))

            # Fill name
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
                    js_fill(page, name_sel, selected_name)
                    safe_print("Name filled.")
                    page.wait_for_timeout(random.randint(500, 1000))
                    js_click_by_text(page, "Continue")
                    safe_print("Continue clicked for name.")
                    name_filled = True
                    break
                ccba_present = page.evaluate("""() => {
                    const radios = document.querySelectorAll('input[name="awsccc-u-rg-ccba-allowed"]');
                    return radios.length > 0;
                }""")
                if ccba_present:
                    safe_print("Accepting CCBA consent...")
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
                safe_print("Name field not found, skipping...")
                js_click_by_text(page, "Continue")
                page.wait_for_timeout(3000)

            # Verification code
            seen_uids = set()
            code_submitted = False
            for attempt in range(3):
                try:
                    code, uid = poll_for_verification_code(generated_email, seen_uids, timeout_seconds=120)
                    seen_uids.add(uid)
                    safe_print(f"Entering verification code: {code}")

                    code_present = page.evaluate("""() => {
                        const el = document.querySelector('input[name="code"], input#code, input[placeholder*="code"]');
                        return !!(el && el.offsetWidth > 0);
                    }""")
                    if code_present:
                        js_fill(page, "input[name='code'], input#code, input[placeholder*='code']", code)
                        page.wait_for_timeout(500)

                    js_click_by_text(page, "Continue") or js_click_by_text(page, "Verify")
                    safe_print("Continue clicked for verification.")
                    page.wait_for_timeout(3000)

                    # Check for error
                    has_error = page.evaluate("""() => {
                        const texts = ["Sorry, that code didn't work", "that code didn't work", "invalid code", "incorrect code"];
                        const body = document.body.textContent.toLowerCase();
                        return texts.some(t => body.includes(t.toLowerCase()));
                    }""")

                    if has_error:
                        safe_print("Error: Code didn't work. Clicking Resend code...")
                        for _ in range(30):
                            resend_clicked = page.evaluate("""() => {
                                const all = Array.from(document.querySelectorAll('button, a'));
                                const target = all.find(el => {
                                    const t = el.textContent.toLowerCase();
                                    return t.includes('resend') && !t.includes('resend code in');
                                });
                                if (!target) return false;
                                target.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                                target.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                                target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                                return true;
                            }""")
                            if resend_clicked:
                                safe_print("Resend code clicked.")
                                page.wait_for_timeout(2000)
                                break
                            page.wait_for_timeout(1000)
                        continue
                    else:
                        code_submitted = True
                        break
                except Exception as e:
                    safe_print(f"Error on verification code step (attempt {attempt + 1}): {e}")
                    page.wait_for_timeout(5000)

            if not code_submitted:
                raise Exception("Failed to verify email address after multiple attempts")

            # Password
            password = generate_secure_password()
            safe_print(f"Generated password: {password}")
            page.wait_for_timeout(random.randint(2000, 4000))

            pw_found = False
            for _ in range(6):
                pw_present = page.evaluate("""() => {
                    const el = document.querySelector('input[type="password"]');
                    return !!(el && el.offsetWidth > 0);
                }""")
                if pw_present:
                    js_fill(page, "input[type='password']", password)
                    safe_print("Password filled.")
                    page.wait_for_timeout(random.randint(500, 1000))
                    js_click_by_text(page, "Continue") or js_click_by_text(page, "Create") or js_click_by_text(page, "Create AWS Builder ID")
                    safe_print("Continue clicked for password. Sign-up completed!")
                    pw_found = True
                    break
                page.wait_for_timeout(3000)

            if not pw_found:
                safe_print("Password fields not found.")

            save_credentials(generated_email, password)
        else:
            safe_print("Continue click skipped.")

    return generated_email


class TimeoutException(Exception):
    pass


def main() -> int:
    args = parse_args()

    try:
        domain = normalize_domain(args.domain)
    except ValueError as error:
        safe_print(f"Input error: {error}")
        return 1

    run_number = 1

    try:
        while True:
            run_once(args, domain, run_number)

            if not args.repeat and not args.immediate:
                input("Press Enter to exit... ")
                return 0

            delay = 0 if args.immediate else args.delay
            if delay > 0:
                safe_print(f"Waiting {delay} seconds before starting the next run...")
                for i in range(delay, 0, -1):
                    try:
                        sys.stdout.write(f"\rNext run starts in {i} seconds... (Ctrl+C to abort) ")
                        sys.stdout.flush()
                    except OSError:
                        pass
                    time.sleep(1)
                safe_print("\rStarting the next run now!")
            else:
                safe_print("Starting the next run immediately!")

            run_number += 1

    except TimeoutException as error:
        safe_print(f"Automation timeout: {error}")
        return 1
    except Exception as error:
        safe_print(f"Unexpected error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
