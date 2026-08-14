"""Headless Kiro refreshToken capture for a freshly-created @havenhaus.in account.

Flow (fully headless):
  1. Launch `kiro-cli login --use-device-flow --license free` (background) -> prints URL + code.
  2. Open the device URL in a HEADLESS Camoufox/Playwright browser.
  3. Log in as <email> with <password> (AWS Builder ID).
  4. If AWS asks for an OTP, read it from the @havenhaus.in mailbox via mail_reader (Gmail OAuth).
  5. Enter the device code.
  6. After kiro-cli exits, read refreshToken from its SQLite DB and write the
     gateway kiro_creds/kiro_newNNN.json + append to credentials.json.

Usage:
  python capture_kiro_token.py <email> <password> [index]
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Make bot modules importable (mail_reader, gmail_oauth)
_BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\automation\automation")
sys.path.insert(0, str(_BOT))

GATEWAY = Path(r"C:\Users\Unkno\Videos\New folder\new try")
CREDS_DIR = GATEWAY / "kiro_creds"
CREDS_JSON = GATEWAY / "credentials.json"
KIRO_DB = Path(r"C:\Users\Unkno\AppData\Local\kiro-cli\data.sqlite3")


def launch_kcli():
    """Start kiro-cli device-flow; return (proc, url, code)."""
    env = dict(os.environ)
    env.pop("HTTPS_PROXY", None)
    env.pop("HTTP_PROXY", None)
    proc = subprocess.Popen(
        ["kiro-cli.exe", "login", "--use-device-flow", "--license", "free"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=env,
    )
    url = code = None
    for _ in range(60):
        line = proc.stdout.readline()
        if not line:
            break
        if "http" in line.lower() and "kiro" in line.lower():
            m = re.search(r"(https?://\S+)", line)
            if m:
                url = m.group(1).strip().strip('"').strip("'")
        m = re.search(r"(?:code|confirm)[^\n]*?([A-Z0-9]{4}-[A-Z0-9]{4})", line, re.I)
        if m:
            code = m.group(1)
        if url and code:
            break
        time.sleep(1)
    return proc, url, code


def read_otp(target_email, timeout=180):
    """Read AWS verification code from the @havenhaus.in mailbox via Gmail OAuth."""
    try:
        from mail_reader import fetch_emails
    except Exception as e:
        print(f"[otp] mail_reader unavailable: {e}")
        return None
    start = time.time()
    seen = set()
    while time.time() - start < timeout:
        try:
            mails = fetch_emails(unread_only=True, limit=10, mark_as_read=False)
            for m in mails:
                if m["uid"] in seen:
                    continue
                seen.add(m["uid"])
                subj = (m.get("subject") or "").lower()
                to = (m.get("to") or "").lower()
                if "verify" in subj and target_email.lower() in to:
                    body = m.get("body_text") or m.get("body_html") or ""
                    mm = re.search(r"\b(\d{6})\b", body)
                    if mm:
                        return mm.group(1)
        except Exception as e:
            print(f"[otp] poll err: {e}")
        time.sleep(5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("password")
    ap.add_argument("index", nargs="?", default="0")
    args = ap.parse_args()

    print(f"[*] Capturing Kiro token for {args.email}")
    proc, url, code = launch_kcli()
    # kiro-cli device-flow prints only the code; the device URL is fixed:
    if not url:
        url = "https://kiro.dev/device"
    print(f"[*] kiro-cli URL : {url}")
    print(f"[*] kiro-cli CODE: {code}")
    if not code:
        print("[!] Failed to get device code")
        proc.terminate()
        return 1

    # Drive the browser headlessly (use Camoufox — bundled browser, no extra install)
    from camoufox.sync_api import Camoufox
    with Camoufox(geoip=False, humanize=True, headless=True, os='windows') as browser:
        page = browser.new_page()
        page.set_default_timeout(60000)
        page.goto(url, timeout=60000)
        page.wait_for_timeout(3000)
        # STEP 1: device code entry (device-flow page shows ONLY a code box first)
        try:
            page.fill('input[name="code"], input#code, input[autocomplete="one-time-code"], input[placeholder*="code"]', code, timeout=15000)
            page.click('button:has-text("Confirm"), button:has-text("Continue"), button:has-text("Verify")', timeout=8000)
            print("[browser] device code entered")
        except Exception as e:
            print(f"[browser] code step: {e}")
        page.wait_for_timeout(5000)

        # STEP 2: AWS Builder ID login (email)
        for _ in range(6):
            try:
                page.fill('input[type="email"]', args.email, timeout=8000)
                page.click('button:has-text("Continue")', timeout=6000)
                print("[browser] email entered")
                break
            except Exception as e:
                page.wait_for_timeout(3000)
        page.wait_for_timeout(5000)

        # STEP 3: password
        for _ in range(6):
            try:
                page.fill('input[type="password"]', args.password, timeout=8000)
                page.click('button:has-text("Continue"), button:has-text("Create")', timeout=6000)
                print("[browser] password entered")
                break
            except Exception as e:
                page.wait_for_timeout(3000)
        page.wait_for_timeout(5000)

        # STEP 4: OTP (if AWS asks)
        try:
            otp_box = page.query_selector('input[name="code"], input#code, input[autocomplete="one-time-code"]')
        except Exception:
            otp_box = None
        if otp_box:
            c = read_otp(args.email)
            if c:
                try:
                    page.fill('input[name="code"], input#code, input[autocomplete="one-time-code"]', c, timeout=8000)
                    page.click('button:has-text("Continue")', timeout=6000)
                    print(f"[browser] OTP {c} entered")
                except Exception as e:
                    print(f"[browser] otp entry: {e}")
        page.wait_for_timeout(5000)

        # STEP 5: Authorize
        for label in ("Authorize", "Allow", "Confirm", "Continue"):
            try:
                page.click(f'button:has-text("{label}")', timeout=5000)
            except Exception:
                pass
        print("[browser] authorize attempted")
        page.wait_for_timeout(8000)
        browser.close()

    # Wait for kiro-cli to finish
    try:
        proc.wait(timeout=30)
    except Exception:
        proc.terminate()

    # Extract refreshToken from kiro-cli DB
    import sqlite3
    if not KIRO_DB.exists():
        print("[!] kiro-cli DB not found")
        return 1
    conn = sqlite3.connect(str(KIRO_DB))
    conn.row_factory = sqlite3.Row
    rt = None
    try:
        for row in conn.execute("SELECT key,value FROM auth_kv"):
            if "refresh" in row["key"].lower():
                rt = row["value"]
        if not rt:
            for row in conn.execute("SELECT key,value FROM state"):
                if "refresh" in row["key"].lower():
                    try:
                        d = json.loads(row["value"])
                        rt = d.get("refreshToken") or d.get("refresh_token")
                    except Exception:
                        pass
    except Exception as e:
        print(f"[db] read err: {e}")
    conn.close()

    if not rt:
        print("[!] No refreshToken found in kiro-cli DB")
        return 1

    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"kiro_new{args.index.zfill(3)}.json"
    fpath = CREDS_DIR / fname
    acc = {
        "refreshToken": rt,
        "authMethod": "builder-id",
        "region": "us-east-1",
        "startUrl": "https://view.awsapps.com/start",
    }
    json.dump(acc, open(fpath, "w", encoding="utf-8"), indent=2)

    existing = []
    if CREDS_JSON.exists():
        try:
            existing = json.load(open(CREDS_JSON, encoding="utf-8"))
        except Exception:
            existing = []
    if not isinstance(existing, list):
        existing = []
    existing.append({
        "type": "json",
        "path": str(fpath),
        "enabled": True,
        "comment": f"Captured {args.email} via headless device-flow",
    })
    json.dump(existing, open(CREDS_JSON, "w", encoding="utf-8"), indent=2)
    print(f"[+] Wrote {fname} and updated credentials.json ({len(existing)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
