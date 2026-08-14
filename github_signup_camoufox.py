#!/usr/bin/env python3
"""
github_signup_camoufox.py  (headless)
Create a GitHub account headless via Camoufox (anti-detect),
using the @havenhaus.in mailbox (readable via Gmail OAuth in this bot dir).
Then we attempt to read the verification email.
"""
import asyncio, sys, json, secrets, string, re, time
from pathlib import Path

BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated")
CLOAK = str(BOT / "CloakBrowser")
sys.path.insert(0, str(BOT / "automation" / "automation"))
sys.path.insert(0, CLOAK)

from camoufox.sync_api import Camoufox
import requests

EMAIL = "github.signup1@havenhaus.in"
USERNAME = "havenhaus" + secrets.token_hex(3)
PASSWORD = "Gh" + secrets.token_urlsafe(14) + "!"

def rand_user():
    return "user" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))

CLICK_JS = """() => {
  const seen = new Set();
  function text(b){return (b.innerText||'').trim().toLowerCase();}
  function clickable(b){
    const t=text(b);
    if(!t) return false;
    if(seen.has(b)) return false;
    if(/github|google|apple/.test(t)) return false;
    if(/(continue|sign up|create|verify|finish|join|submit|confirm)/.test(t)){
      seen.add(b); b.click(); return true;
    }
    return false;
  }
  document.querySelectorAll('button,a,input[type=submit]').forEach(clickable);
}"""

def get_latest_otp():
    # read @havenhaus.in OTP via Gmail OAuth (mail_reader)
    try:
        import mail_reader as mr
        msgs = mr.fetch_emails(folder="INBOX", unread_only=False, limit=15, mark_as_read=False)
        for m in msgs:
            sender = (m.get("from") or "").lower()
            if "github" not in sender:
                continue
            body = m.get("body") or m.get("snippet") or ""
            code = re.search(r"\\b\\d{6}\\b", body)
            if code:
                return code.group(0)
    except Exception as e:
        print("[dbg] gmail otp err:", e)
    return None

def main():
    print(f"[*] GitHub signup: {EMAIL} / user={USERNAME}", flush=True)
    with Camoufox(geoip=False, humanize=True, headless=True, args=["--no-sandbox","--disable-gpu"], os="windows") as browser:
        page = browser.new_page()
        page.goto("https://github.com/signup", timeout=60000)
        time.sleep(4)
        # fill email
        try:
            page.fill('input[id="user_email"], input[name="user[email]"]', EMAIL, timeout=8000)
            print("[+] email filled", flush=True)
        except Exception as e:
            print("[!] email fill err:", e, flush=True)
        time.sleep(1)
        page.evaluate(CLICK_JS); time.sleep(2)
        # password
        try:
            page.fill('input[id="user_password"], input[name="user[password]"]', PASSWORD, timeout=8000)
            print("[+] password filled", flush=True)
        except Exception as e:
            print("[!] password fill err:", e, flush=True)
        time.sleep(1)
        page.evaluate(CLICK_JS); time.sleep(2)
        # username
        try:
            page.fill('input[id="user_login"], input[name="user[login]"]', USERNAME, timeout=8000)
            print("[+] username filled", flush=True)
        except Exception as e:
            print("[!] username fill err:", e, flush=True)
        time.sleep(1)
        page.evaluate(CLICK_JS); time.sleep(2)
        # maybe uncheck email preferences
        try:
            cb = page.locator('input[name="user[email_preference]"]')
            if cb.count() and cb.first.is_checked():
                cb.first.uncheck()
        except Exception:
            pass
        page.evaluate(CLICK_JS); time.sleep(3)
        # captcha / puzzle? GitHub uses a puzzle sometimes. Try to solve if present.
        # OTP
        print("[*] waiting for GitHub verification email...", flush=True)
        otp = None
        for i in range(30):
            otp = get_latest_otp()
            if otp:
                print(f"[+] OTP received: {otp}", flush=True)
                break
            time.sleep(4)
        if otp:
            try:
                page.fill('input[id="otp"], input[name="otp"], input[inputmode="numeric"]', otp, timeout=8000)
                print("[+] OTP filled", flush=True)
                page.evaluate(CLICK_JS); time.sleep(3)
            except Exception as e:
                print("[!] otp fill err:", e, flush=True)
        else:
            print("[!] NO OTP received (GitHub may have blocked signup)", flush=True)
        time.sleep(3)
        print("[*] final url:", page.url, flush=True)
        print(f"[RESULT] email={EMAIL} username={USERNAME} password={PASSWORD}", flush=True)
        # save creds
        out = {"email": EMAIL, "username": USERNAME, "password": PASSWORD, "url": page.url}
        json.dump(out, open(str(BOT / "github_created.json"), "w", encoding="utf-8"), indent=2)
        print("[+] saved github_created.json", flush=True)

if __name__ == "__main__":
    main()
