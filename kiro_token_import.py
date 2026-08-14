"""Kiro Token Import / Persistent Login Script
================================================
Cross-platform version (Windows + Linux + macOS)

This script automates the Kiro Builder ID login flow to capture
refresh tokens WITHOUT needing kiro-cli or manual browser interaction.

Flow:
  1. Register OIDC client with AWS
  2. Open Kiro sign-in page in headless browser
  3. Click AWS Builder ID
  4. Fill email + password (Builder ID credentials)
  5. If OTP required, read from disposable email (mailtm/1secmail) or IMAP
  6. Click Allow/Authorize
  7. Exchange auth code for tokens
  8. Save tokens to kiro_creds/ + credentials.json

Usage:
  python kiro_token_import.py <email> <password> [index]
  python kiro_token_import.py --batch accounts.csv

Token files are saved as: kiro_creds/kiro_newNNN.json
Each token can be reused for Kiro CLI login:
  kiro-cli login --token-file kiro_creds/kiro_new001.json
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import csv
import hashlib
import json
import os
import secrets
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

# ── Paths (cross-platform) ───────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
CREDS_DIR = SCRIPT_DIR / "kiro_creds"
CREDS_JSON = SCRIPT_DIR / "credentials.json"
KIRO_DB_LINUX = Path.home() / ".config" / "kiro-cli" / "data.sqlite3"
KIRO_DB_WIN = Path(os.environ.get("LOCALAPPDATA", "")) / "kiro-cli" / "data.sqlite3"
KIRO_DB_MAC = Path.home() / "Library" / "Application Support" / "kiro-cli" / "data.sqlite3"

# ── OIDC Constants ───────────────────────────────────────────────────────────
REG_OIDC = "https://oidc.us-east-1.amazonaws.com"
REG_SCOPES = [
    "codewhisperer:completions", "codewhisperer:analysis",
    "codewhisperer:conversations", "codewhisperer:transformations",
    "codewhisperer:taskassist",
]
CALLBACK_PORT = 3128
REG_REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}"
KIRO_SIGNIN_URL = "https://app.kiro.dev/signin"
ISSUER_URL = "https://view.awsapps.com/start/"
REG_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode()).hexdigest()


def find_kiro_db() -> Path | None:
    """Find kiro-cli SQLite database across platforms."""
    for p in [KIRO_DB_LINUX, KIRO_DB_WIN, KIRO_DB_MAC]:
        if p.exists():
            return p
    return None


def read_otp_imap(target_email: str, timeout: int = 180) -> str | None:
    """Read OTP from Gmail/IMAP mailbox."""
    try:
        from mail_reader import fetch_emails
        start = time.time()
        seen = set()
        while time.time() - start < timeout:
            try:
                mails = fetch_emails(unread_only=True, limit=12, mark_as_read=False)
                for m in mails:
                    uid = m.get("uid", "")
                    if uid in seen:
                        continue
                    seen.add(uid)
                    to = (m.get("to") or "").lower()
                    subj = (m.get("subject") or "").lower()
                    body = (m.get("body_text") or m.get("body_html") or "")
                    if target_email.lower() in to:
                        if ("aws" in subj or "verify" in subj or "code" in subj or "otp" in subj):
                            import re
                            mm = re.search(r"\b(\d{6})\b", body)
                            if mm:
                                return mm.group(1)
            except Exception as e:
                print(f"[otp] poll err: {e}")
            time.sleep(6)
    except ImportError:
        print("[otp] mail_reader not available")
    return None


def read_otp_disposable(provider, target_email: str, timeout: int = 180) -> str | None:
    """Read OTP from disposable email provider (mailtm/1secmail/fake.legal)."""
    import re
    start = time.time()
    print(f"[otp] Waiting for OTP on {provider.address}...")
    while time.time() - start < timeout:
        try:
            emails = provider.get_inbox()
            if emails:
                for em in emails:
                    body = em.get("body_text", "") or em.get("body_html", "")
                    mm = re.search(r"\b(\d{6})\b", body)
                    if mm:
                        return mm.group(1)
                    # Also check subject for 6-digit code
                    subj = em.get("subject", "")
                    mm2 = re.search(r"\b(\d{6})\b", subj)
                    if mm2:
                        return mm2.group(1)
        except Exception as e:
            print(f"[otp] poll err: {e}")
        time.sleep(5)
    return None


def persist_token(
    path: Path,
    client_id: str,
    client_secret: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    email: str,
    auth_method: str = "IdC",
    provider_name: str = "BuilderId",
):
    """Write token JSON + update credentials.json index."""
    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    acc = {
        "refreshToken": refresh_token,
        "accessToken": access_token,
        "clientId": client_id,
        "clientSecret": client_secret,
        "region": "us-east-1",
        "startUrl": ISSUER_URL,
        "authMethod": auth_method,
        "provider": provider_name,
        "expiresAt": expires_at,
        "email": email,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(acc, open(path, "w", encoding="utf-8"), indent=2)

    # Update credentials.json
    existing = []
    if CREDS_JSON.exists():
        try:
            existing = json.load(open(CREDS_JSON, encoding="utf-8"))
        except Exception:
            existing = []
    if not isinstance(existing, list):
        existing = []
    if not any(str(e.get("path")) == str(path) for e in existing if isinstance(e, dict)):
        existing.append({
            "type": "json",
            "path": str(path),
            "enabled": True,
            "comment": f"Captured {email} via headless Builder ID login",
        })
        json.dump(existing, open(CREDS_JSON, "w", encoding="utf-8"), indent=2)
    print(f"[+] Wrote {path.name} + updated credentials.json ({len(existing)} entries)")


async def run_single(email: str, password: str, index: str, mail_provider=None):
    """Run the full login + token capture flow for one account."""
    print(f"\n{'='*60}")
    print(f"  Token Import: {email} (#{index})")
    print(f"{'='*60}")

    # Try Playwright first (works without Camoufox)
    use_playwright = True
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        try:
            from camoufox.async_api import AsyncCamoufox
            use_playwright = False
            print("[*] Using Camoufox (bundled browser)")
        except ImportError:
            print("[!] Neither Playwright nor Camoufox available")
            return 1

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())
    state_val = secrets.token_urlsafe(32)

    # Register OIDC client
    print("[*] Registering OIDC client...")
    import requests
    try:
        reg = requests.post(f"{REG_OIDC}/client/register", json={
            "clientName": "Kiro IDE",
            "clientType": "public",
            "grantTypes": ["authorization_code", "refresh_token"],
            "issuerUrl": ISSUER_URL,
            "redirectUris": [REG_REDIRECT_URI],
            "scopes": REG_SCOPES,
        }, timeout=25, verify=False).json()
    except Exception as e:
        print(f"[!] OIDC register error: {e}")
        return 1
    if "clientId" not in reg:
        print(f"[!] OIDC register failed: {reg}")
        return 1
    client_id, client_secret = reg["clientId"], reg["clientSecret"]
    print(f"[+] OIDC client: {client_id[:20]}...")

    # Build sign-in URL
    signin_url = f"{KIRO_SIGNIN_URL}?" + urlencode({
        "state": state_val,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": REG_REDIRECT_URI,
        "redirect_from": "KiroIDE",
    })

    # Start callback server
    auth_code_holder = {"code": ""}
    import re

    class CB(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            c = qs.get("code", [""])[0]
            if c:
                auth_code_holder["code"] = c
                print(f"[+] callback got code: {c[:12]}...")
            # Also capture signin callback params
            login_option = qs.get("login_option", [""])[0]
            issuer_url = qs.get("issuer_url", [""])[0]
            if login_option:
                auth_code_holder["signin_params"] = {
                    "login_option": login_option,
                    "issuer_url": issuer_url,
                    "state": qs.get("state", [""])[0],
                }
                print(f"[+] callback got signin params: {login_option}, {issuer_url[:50]}")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Authorization successful. You can close this tab.</body></html>")
        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), CB)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[+] Callback server on 127.0.0.1:{CALLBACK_PORT}")

    if use_playwright:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page()
            page.set_default_timeout(60000)

            # Navigate to Kiro sign-in
            print(f"[*] Navigating to Kiro sign-in...")
            await page.goto(signin_url, timeout=60000)
            await asyncio.sleep(3)

            # Click AWS Builder ID
            clicked = False
            for label in ["AWS Builder ID", "Builder ID"]:
                try:
                    btn = page.locator(f"button:has-text('{label}')").first
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click()
                        clicked = True
                        print(f"[+] Clicked {label}")
                        break
                except Exception:
                    pass

            if not clicked:
                # JS fallback
                clicked = await page.evaluate("""() => {
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const t = (el.textContent || '').trim();
                        if ((t.includes('AWS Builder ID') || t.includes('Builder ID'))
                            && el.offsetWidth > 0 && el.offsetHeight > 0
                            && !['BODY','HTML','MAIN'].includes(el.tagName)) {
                            el.click();
                            return t.substring(0, 40);
                        }
                    }
                    return '';
                }""")
                if clicked:
                    print(f"[+] Clicked (JS): {clicked}")

            await asyncio.sleep(5)

            # Wait for signin callback, then navigate to OIDC authorize
            print("[*] Waiting for signin callback...")
            for _ in range(30):
                await asyncio.sleep(2)
                if auth_code_holder.get("signin_params"):
                    print(f"[+] Signin callback received!")
                    break
            
            # Navigate to OIDC authorize URL
            signin_params = auth_code_holder.get("signin_params", {})
            if signin_params and client_id:
                code_verifier_val = auth_code_holder.get("code_verifier", "")
                if not code_verifier_val:
                    code_verifier_val = secrets.token_urlsafe(64)
                    auth_code_holder["code_verifier"] = code_verifier_val
                code_challenge = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier_val.encode()).digest()
                ).rstrip(b"=").decode()
                authorize_url = f"{REG_OIDC}/authorize?" + urlencode({
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": REG_REDIRECT_URI,
                    "scopes": ",".join(REG_SCOPES),
                    "state": signin_params.get("state", state_val),
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                })
                print(f"[*] Navigating to OIDC authorize...")
                try:
                    await page.goto(authorize_url, wait_until="domcontentloaded", timeout=60000)
                    print(f"[+] OIDC page loaded (networkidle)")
                except Exception as e:
                    print(f"[!] OIDC navigate error: {e}")
                # Wait for the AWS login page to render
                for _wait in range(15):
                    await asyncio.sleep(2)
                    try:
                        body_text = await page.evaluate("document.body ? document.body.innerText || '' : ''")
                        if len(body_text) > 50 or "Get started" in body_text or "Email" in body_text:
                            print(f"[+] AWS login page rendered: {len(body_text)} chars")
                            break
                    except:
                        pass
                else:
                    print("[!] AWS login page did not render within 30s")
                # Take screenshot for debugging
                try:
                    await page.screenshot(path=f"/tmp/kiro_step_{step if 'step' in dir() else 0}.png")
                except:
                    pass
            
            # State machine: email -> password -> otp -> allow
            for step in range(90):
                if auth_code_holder["code"]:
                    break

                url = page.url

                # Skip chrome-error pages
                if url.startswith("chrome-error"):
                    print(f"  [!] Chrome error page detected, waiting...")
                    await asyncio.sleep(3)
                    continue
                # Check if on AWS sign-in page
                if "signin.aws" in url or "profile.aws" in url or "sso" in url:
                    if step % 10 == 0:
                        try:
                            body = await page.evaluate("document.body ? document.body.innerText.slice(0,200) : 'no body'")
                            print(f"  [dbg] step={step} url={url[:60]} body={body[:80]}")
                        except:
                            pass

                # EMAIL
                try:
                    ei = page.locator('input[type="email"]').first
                    if await ei.count() > 0 and await ei.first.is_visible():
                        cur = await ei.first.input_value()
                        if cur != email:
                            await ei.first.fill(email)
                            await asyncio.sleep(0.5)
                            # Use native click instead of JS evaluate
                            try:
                                continue_btn = page.locator('button:has-text("Continue")').first
                                await continue_btn.click(timeout=10000)
                                print(f"[+] Email filled + Continue clicked: {email}")
                            except Exception:
                                # Fallback to JS
                                await page.evaluate("""() => {
                                    document.querySelectorAll('button').forEach(b => {
                                        const t = (b.innerText || '').toLowerCase();
                                        if (t.includes('continue') || t.includes('next')) b.click();
                                    });
                                }""")
                                print(f"[+] Email filled (JS fallback): {email}")
                            await asyncio.sleep(5)
                except Exception:
                    pass

                # PASSWORD
                try:
                    pi = page.locator('input[type="password"]').first
                    if await pi.count() > 0 and await pi.first.is_visible():
                        cur = await pi.first.input_value()
                        if cur != password:
                            await pi.first.fill(password)
                            await asyncio.sleep(0.5)
                            # Use native click
                            try:
                                signin_btn = page.locator('button:has-text("Sign in")').first
                                await signin_btn.click(timeout=10000)
                                print("[+] Password filled + Sign in clicked")
                            except Exception:
                                try:
                                    submit_btn = page.locator('button[type="submit"]').first
                                    await submit_btn.click(timeout=5000)
                                    print("[+] Password filled + Submit clicked")
                                except Exception:
                                    await page.evaluate("""() => {
                                        document.querySelectorAll('button').forEach(b => {
                                            const t = (b.innerText || '').toLowerCase();
                                            if (t.includes('sign') || t.includes('submit')) b.click();
                                        });
                                    }""")
                                    print("[+] Password filled (JS fallback)")
                            await asyncio.sleep(5)
                except Exception:
                    pass

                # OTP
                try:
                    otp_input = page.locator(
                        'input[autocomplete="one-time-code"], '
                        'input[autocomplete="off"][maxlength="6"], '
                        'input#code, input[name="code"]'
                    ).first
                    if await otp_input.count() > 0 and await otp_input.first.is_visible():
                        otp = None
                        if mail_provider:
                            otp = read_otp_disposable(mail_provider, email, timeout=120)
                        if not otp:
                            otp = read_otp_imap(email, timeout=120)
                        if otp:
                            await otp_input.first.fill(otp)
                            await asyncio.sleep(0.5)
                            await page.evaluate("""() => {
                                document.querySelectorAll('button').forEach(b => {
                                    const t = (b.innerText || '').toLowerCase();
                                    if (t.includes('continue') || t.includes('verify')) b.click();
                                });
                            }""")
                            print(f"[+] OTP filled: {otp}")
                            await asyncio.sleep(5)
                except Exception:
                    pass

                # ALLOW / AUTHORIZE
                try:
                    allow_clicked = await page.evaluate("""() => {
                        let clicked = '';
                        document.querySelectorAll('button').forEach(b => {
                            const t = (b.innerText || '').toLowerCase();
                            if ((t.includes('allow') || t.includes('authorize') ||
                                 t.includes('confirm') || t.includes('agree') ||
                                 t.includes('accept')) && b.offsetWidth > 0) {
                                b.click();
                                clicked = t;
                            }
                        });
                        return clicked;
                    }""")
                    if allow_clicked:
                        print(f"[+] Clicked: {allow_clicked}")
                        await asyncio.sleep(5)
                except Exception:
                    pass

                # Check for success indicators
                if auth_code_holder["code"]:
                    break
                if step % 10 == 0:
                    print(f"  [step {step}] URL: {url[:80]}")

            await browser.close()

    server.shutdown()

    # Exchange code for tokens
    code = auth_code_holder["code"]
    if not code:
        print("[!] No authorization code captured")
        return 1
    print(f"[+] Authorization code: {code[:12]}...")

    tok = requests.post(f"{REG_OIDC}/token", json={
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": "authorization_code",
        "code": code,
        "redirectUri": REG_REDIRECT_URI,
        "codeVerifier": code_verifier,
    }, timeout=25, verify=False).json()

    if "accessToken" not in tok:
        print(f"[!] Token exchange failed: {json.dumps(tok)[:300]}")
        return 1

    expires_in = tok.get("expiresIn", 28800)
    fname = f"kiro_new{index.zfill(3)}.json"
    persist_token(
        CREDS_DIR / fname,
        client_id, client_secret,
        tok["accessToken"], tok["refreshToken"],
        expires_in, email,
    )

    print(f"\n{'='*60}")
    print(f"  SUCCESS! Token saved: kiro_creds/{fname}")
    print(f"  Refresh: {tok['refreshToken'][:30]}...")
    print(f"{'='*60}")
    return 0


def run_batch(csv_path: str, mail_provider=None):
    """Process a CSV file with email,password pairs."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Skip header if present
    if rows and ("email" in rows[0][0].lower() or "password" in rows[0][1].lower() if len(rows[0]) > 1 else False):
        rows = rows[1:]

    results = []
    for i, row in enumerate(rows):
        if len(row) < 2:
            continue
        email, password = row[0].strip(), row[1].strip()
        if not email or not password:
            continue
        print(f"\n{'─'*50}")
        print(f"  Processing {i+1}/{len(rows)}: {email}")
        rc = asyncio.run(run_single(email, password, str(i+1), mail_provider))
        results.append({"email": email, "success": rc == 0})
        time.sleep(2)  # Rate limit

    print(f"\n{'='*60}")
    print(f"  BATCH COMPLETE: {sum(1 for r in results if r['success'])}/{len(results)} succeeded")
    print(f"{'='*60}")
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Kiro Token Import - Capture Builder ID tokens headlessly"
    )
    ap.add_argument("email", nargs="?", help="Builder ID email")
    ap.add_argument("password", nargs="?", help="Builder ID password")
    ap.add_argument("index", nargs="?", default="0", help="Account index (0-based)")
    ap.add_argument("--batch", help="CSV file with email,password pairs")
    ap.add_argument(
        "--mail-provider",
        default="mailtm",
        choices=["mailtm", "1secmail", "fake.legal"],
        help="Disposable email provider for OTP (default: mailtm)",
    )
    ap.add_argument("--headless", action="store_true", default=True, help="Run headless (default)")
    ap.add_argument("--visible", action="store_true", help="Run with visible browser")
    args = ap.parse_args()

    if args.batch:
        return run_batch(args.batch)

    if not args.email or not args.password:
        print("Usage:")
        print("  python kiro_token_import.py <email> <password> [index]")
        print("  python kiro_token_import.py --batch accounts.csv")
        print()
        print("Options:")
        print("  --mail-provider mailtm|1secmail|fake.legal  OTP source")
        return 2

    return asyncio.run(run_single(args.email, args.password, args.index))


if __name__ == "__main__":
    raise SystemExit(main())
