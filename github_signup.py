"""Headless GitHub account creation via Camoufox (stealth).

Creates a GitHub account with a fresh @havenhaus.in email, reads the
verification code from the @havenhaus.in mailbox (via Gmail OAuth / mail_reader),
and confirms the address. Writes the new creds to github_accounts.csv.

Usage:
  python github_signup.py
"""
from __future__ import annotations
import csv
import json
import random
import re
import string
import sys
import time
from pathlib import Path

_BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\automation\automation")
sys.path.insert(0, str(_BOT))

OUT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\github_accounts.csv")


def gen_ident():
    adj = ["blue", "fast", "cool", "red", "silent", "bright", "calm", "swift", "tiny", "bold"]
    noun = ["tiger", "river", "comet", "falcon", "maple", "echo", "nova", "pixel", "delta", "wolf"]
    base = f"{random.choice(adj)}{random.choice(noun)}{random.randint(100,999)}"
    email = f"{base}@havenhaus.in"
    pwd = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%", k=16))
    return base, email, pwd


def read_github_code(target_email, timeout=180):
    try:
        import logging as _lg
        for _n in list(_lg.root.manager.loggerDict):
            _lg.getLogger(_n).disabled = True
        _lg.getLogger().disabled = True
        from mail_reader import fetch_emails
    except Exception as e:
        print(f"[otp] mail_reader err: {e}")
        return None
    start = time.time()
    seen = set()
    while time.time() - start < timeout:
        try:
            mails = fetch_emails(unread_only=True, limit=12, mark_as_read=False)
            for m in mails:
                if m["uid"] in seen:
                    continue
                seen.add(m["uid"])
                to = (m.get("to") or "").lower()
                subj = (m.get("subject") or "").lower()
                body = (m.get("body_text") or m.get("body_html") or "")
                if target_email.lower() in to and ("github" in subj or "verify" in subj or "code" in subj):
                    mm = re.search(r"\b(\d{4,8})\b", body)
                    if mm:
                        return mm.group(1)
                # GitHub sometimes sends just "123456" as code in body
                if target_email.lower() in to and re.search(r"\b\d{6}\b", body):
                    return re.search(r"\b(\d{6})\b", body).group(1)
        except Exception as e:
            print(f"[otp] poll err: {e}")
        time.sleep(6)
    return None


def main():
    from camoufox.sync_api import Camoufox
    import logging as _lg
    # Silence emoji logging from mail_reader/gmail_oauth to avoid cp1252 crash
    @staticmethod
    def _noop(*a, **k):
        pass
    _lg.StreamHandler.emit = _noop

    username, email, pwd = gen_ident()
    print(f"[*] GitHub signup: username={username} email={email}")

    with Camoufox(geoip=False, humanize=True, headless=True, os='windows') as b:
        p = b.new_page()
        p.set_default_timeout(20000)
        p.goto("https://github.com/join", timeout=40000)
        p.wait_for_timeout(3000)
        # Fill form
        try:
            p.fill('input[id="user_login"], input[name="user[login]"]', username, timeout=10000)
            print("[+] username filled")
        except Exception as e:
            print(f"[!] username fill: {e}")
        try:
            p.fill('input[id="user_email"], input[name="user[email]"]', email, timeout=10000)
            print("[+] email filled")
        except Exception as e:
            print(f"[!] email fill: {e}")
        try:
            p.fill('input[id="user_password"], input[name="user[password]"]', pwd, timeout=10000)
            print("[+] password filled")
        except Exception as e:
            print(f"[!] password fill: {e}")
        # Uncheck marketing email if present
        try:
            for cb in p.query_selector_all('input[type="checkbox"]'):
                try:
                    if cb.is_checked():
                        cb.uncheck()
                except Exception:
                    pass
        except Exception:
            pass
        # Click any human-verification checkbox (GitHub sometimes shows one)
        try:
            for el in p.query_selector_all('input[type="checkbox"], iframe'):
                if 'robot' in (el.get_attribute('aria-label') or '').lower() or 'human' in (el.inner_text() or '').lower():
                    el.click(timeout=5000)
                    print("[+] human-verify clicked")
        except Exception:
            pass
        # Submit
        try:
            p.click('button:has-text("Sign up"), button[type="submit"]', timeout=8000)
            print("[+] submit clicked")
        except Exception as e:
            print(f"[!] submit: {e}")
        p.wait_for_timeout(6000)

        # GitHub may show a "human verification" / puzzle. Report if present.
        content = p.content().lower()
        if "verify you are human" in content or "puzzle" in content or "are you a robot" in content:
            print("[!] GitHub human-verification challenge detected — attempting checkbox click")
            try:
                p.click('input[type="checkbox"]', timeout=5000)
            except Exception:
                pass
            p.wait_for_timeout(4000)

        # Read verification code from mailbox (longer wait)
        code = read_github_code(email, timeout=240)
        print(f"[*] GitHub verification code: {code}")
        if code:
            try:
                p.fill('input[name="code"], input#code, input[autocomplete="one-time-code"]', code, timeout=10000)
                p.click('button:has-text("Verify"), button:has-text("Continue")', timeout=8000)
                print("[+] code submitted")
            except Exception as e:
                print(f"[!] code submit: {e}")
            p.wait_for_timeout(5000)

        # Save state
        OUT.parent.mkdir(parents=True, exist_ok=True)
        fe = OUT.exists()
        with open(OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not fe:
                w.writerow(["username", "email", "password", "ts"])
            w.writerow([username, email, pwd, time.strftime("%Y-%m-%d %H:%M:%S")])
        print(f"[+] Saved GitHub account to {OUT}")

        # Clear cookies as requested after capture
        try:
            p.context.clear_cookies()
            print("[+] cookies cleared")
        except Exception as e:
            print(f"[!] cookie clear: {e}")
    print("[done]")


if __name__ == "__main__":
    main()
