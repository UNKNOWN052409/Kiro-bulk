#!/usr/bin/env python3
"""
Kiro Account Creator — fixed, consolidated version
Creates AWS Builder ID accounts via Camoufox anti-detect browser.
Auto-OTP via Gmail IMAP OAuth2, adds to 9Router panel.
"""
import base64, csv, hashlib, json, os, random, re, secrets, socket, string, sys, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from camoufox.sync_api import Camoufox
import requests

# ── Suppress noisy lib logging ──────────────────────────────────────────────
import logging as _logging
for _lg in ['gmail_oauth', 'mail_reader', 'google.auth', 'google_auth_oauthlib']:
    _log = _logging.getLogger(_lg)
    _log.setLevel(_logging.CRITICAL); _log.handlers.clear(); _log.propagate = False

try:
    from mail_reader import fetch_emails, mark_email_read
    MAIL_OK = True
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from mail_reader import fetch_emails, mark_email_read
        MAIL_OK = True
    except ImportError:
        MAIL_OK = False

# ── Constants ────────────────────────────────────────────────────────────────
PROXYRISE_API_KEY = "pgw-d890748b9e9c734c66a3c1a327fd1db84724cad6cbbe440d"
PROXYRISE_ENDPOINT = "172.65.145.196:3389"
KIRO_SIGNIN = "https://app.kiro.dev/signin"
REG_OIDC = "https://oidc.us-east-1.amazonaws.com"
REG_REDIRECT_URI = "http://127.0.0.1:3128"
REG_SCOPES = [
    "codewhisperer:completions", "codewhisperer:analysis",
    "codewhisperer:conversations", "codewhisperer:transformations",
    "codewhisperer:taskassist",
]
ISSUER_URL = "https://view.awsapps.com/start/"

def _b64url(d):
    return base64.urlsafe_b64encode(d).decode().rstrip("=")

# OIDC state (shared across calls)
_oidc_client = {"client_id": None, "code_verifier": None, "code_challenge": None, "state_val": None, "signin_url": None}
_callback_server = {"instance": None, "signin_params": {}, "auth_code": ""}

def _start_callback_server():
    """Start the local callback server to capture Kiro signin redirects."""
    if _callback_server["instance"] is not None:
        return True
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 3128))
        s.close()
    except OSError:
        try:
            os.system("lsof -tiTCP:3128 -sTCP:LISTEN 2>/dev/null | xargs -r kill -9")
            time.sleep(1)
        except Exception:
            pass

    class CbHandler(BaseHTTPRequestHandler):
        def do_GET(self_h):
            parsed = urlparse(self_h.path)
            qs = parse_qs(parsed.query)
            code = qs.get("code", [""])[0]
            if code:
                _callback_server["auth_code"] = code
                self_h.send_response(200)
                self_h.send_header("Content-Type", "text/html")
                self_h.end_headers()
                self_h.wfile.write(b"<html><body><h2>Done</h2></body></html>")
            elif "signin/callback" in parsed.path or qs.get("login_option"):
                _callback_server["signin_params"] = {k: v[0] for k, v in qs.items()}
                sp("    [CB] Signin callback received")
                self_h.send_response(200)
                self_h.send_header("Content-Type", "text/html")
                self_h.end_headers()
                self_h.wfile.write(b"<html><body><p>Redirecting...</p></body></html>")
            else:
                self_h.send_response(200)
                self_h.send_header("Content-Type", "text/html")
                self_h.end_headers()
                self_h.wfile.write(b"<html><body><p>OK</p></body></html>")
        def log_message(self_h, *args):
            pass

    server = HTTPServer(("127.0.0.1", 3128), CbHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _callback_server["instance"] = server
    sp("  [*] Callback server started on 127.0.0.1:3128")
    return True

def _register_oidc_client():
    """Register a fresh OIDC client with AWS for PKCE auth flow."""
    if _oidc_client["client_id"] is not None:
        return True

    _oidc_client["code_verifier"] = secrets.token_urlsafe(64)
    _oidc_client["code_challenge"] = _b64url(
        hashlib.sha256(_oidc_client["code_verifier"].encode()).digest()
    )
    _oidc_client["state_val"] = secrets.token_urlsafe(32)

    try:
        resp = requests.post(f"{REG_OIDC}/client/register", json={
            "clientName": "Kiro IDE", "clientType": "public",
            "grantTypes": ["authorization_code", "refresh_token"],
            "issuerUrl": ISSUER_URL,
            "redirectUris": [REG_REDIRECT_URI], "scopes": REG_SCOPES,
        }, timeout=25, verify=False)
        reg = resp.json()
        if "clientId" not in reg:
            sp(f"  [!] OIDC registration failed: {reg}")
            return False
        _oidc_client["client_id"] = reg["clientId"]
        sp(f"  [+] OIDC client registered: {_oidc_client['client_id'][:20]}...")

        _oidc_client["signin_url"] = f"{KIRO_SIGNIN}?" + urlencode({
            "state": _oidc_client["state_val"],
            "code_challenge": _oidc_client["code_challenge"],
            "code_challenge_method": "S256",
            "redirect_uri": REG_REDIRECT_URI,
            "redirect_from": "KiroIDE",
        })
        return True
    except Exception as e:
        sp(f"  [!] OIDC registration error: {e}")
        return False

def _navigate_to_oidc_authorize(page):
    """Build and navigate to the OIDC authorize URL after Builder ID callback."""
    if not _oidc_client["client_id"]:
        return False
    params = _callback_server["signin_params"]
    if not params:
        sp("  [!] No signin callback params received")
        return False

    authorize_url = f"{REG_OIDC}/authorize?" + urlencode({
        "response_type": "code",
        "client_id": _oidc_client["client_id"],
        "redirect_uri": REG_REDIRECT_URI,
        "scopes": ",".join(REG_SCOPES),
        "state": params.get("state", _oidc_client["state_val"]),
        "code_challenge": _oidc_client["code_challenge"],
        "code_challenge_method": "S256",
    })
    sp(f"  [+] Navigating to OIDC authorize...")
    page.goto(authorize_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(random.randint(2000, 4000))
    return True
CSV_FILE = Path(__file__).parent / "kiro_accounts.csv"

FIRST_NAMES = [
    "James","Maria","John","Emma","Robert","Olivia","Michael","Sophia",
    "David","Isabella","William","Mia","Richard","Charlotte","Joseph","Amelia",
    "Thomas","Evelyn","Charles","Abigail","Daniel","Emily","Matthew","Harper",
    "Anthony","Ella","Mark","Scarlett","Steven","Grace","Andrew","Chloe",
    "Kenneth","Victoria","Joshua","Natalie","Kevin","Riley","Brian","Zoe",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def safe_print(*args, **kwargs):
    """Safe print — survives redirected stdout on Windows."""
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        try:
            s = ' '.join(str(a) for a in args)
            print(s.encode('ascii', errors='replace').decode('ascii'), **kwargs)
        except Exception:
            pass

def sp(*args, **kwargs):
    return safe_print(*args, **kwargs)

def load_proxy_settings():
    cfg = os.path.expanduser("~/.proxy_cli/settings.json")
    if os.path.exists(cfg):
        with open(cfg) as f:
            s = json.load(f)
            return s.get("api_key", PROXYRISE_API_KEY), s.get("endpoint", PROXYRISE_ENDPOINT)
    return PROXYRISE_API_KEY, PROXYRISE_ENDPOINT

def get_proxy(country="us"):
    api_key, endpoint = load_proxy_settings()
    return {'server': f'http://{endpoint}', 'username': f'res-{country}', 'password': api_key}

def gen_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def gen_email(name, domain):
    parts = name.lower().split()
    return f"{parts[0]}{parts[-1]}@{domain}"

def gen_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    pw = [random.choice(string.ascii_uppercase), random.choice(string.ascii_lowercase),
          random.choice(string.digits), random.choice("!@#$%^&*()_+-=")]
    pw += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(pw)
    return "".join(pw)

def parse_interval(raw):
    raw = raw.strip().lower()
    total = 0.0
    m = re.findall(r'(\d+(?:\.\d+)?)\s*m', raw)
    s = re.findall(r'(\d+(?:\.\d+)?)\s*s', raw)
    if m: total += sum(float(x) * 60 for x in m)
    if s: total += sum(float(x) for x in s)
    if total == 0:
        try: total = float(raw)
        except ValueError: total = 120.0
    return total

def fmt_time(sec):
    m, s = int(sec) // 60, int(sec) % 60
    return f"{m}m {s}s" if m else f"{s}s"

# ── Playwright helpers — use native locator API (React-safe) ─────────────────

def click_by_text(page, text, exact=False, timeout=10000):
    """Click a button/ link by text using Playwright native click (React-safe)."""
    try:
        if exact:
            loc = page.locator(f"button:has-text('{text}'), a:has-text('{text}'), [role='button']:has-text('{text}')").first
            loc.click(timeout=timeout)
            return True
        # For partial match, use filter
        for tag in ["button", "a", '[role="button"]']:
            loc = page.locator(f"{tag}").filter(has_text=text).first
            if loc.is_visible(timeout=2000):
                loc.click(timeout=timeout)
                return True
    except Exception:
        pass
    return False

def fill_field(page, selector, value):
    """Fill a form field via Playwright native fill (React-safe)."""
    try:
        loc = page.locator(selector).first
        if loc.is_visible(timeout=5000):
            loc.click(timeout=3000)
            page.wait_for_timeout(random.randint(100, 300))
            loc.fill(value)
            page.wait_for_timeout(random.randint(100, 300))
            return True
    except Exception:
        pass
    return False

def fill_field_js(page, selector, value):
    """Fill form field via JS value setter (fallback for tricky pages)."""
    return page.evaluate(f"""() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el || el.offsetWidth <= 0) return false;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(el, {json.dumps(value)});
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        el.dispatchEvent(new Event('blur', {{bubbles: true}}));
        return true;
    }}""")

def click_js(page, text, exact=False):
    """Fallback JS click — use MouseEvent (less reliable with React, kept for headless edge cases)."""
    return page.evaluate(f"""() => {{
        const all = Array.from(document.querySelectorAll('button, a, [role="button"]'));
        const target = exact
            ? all.find(el => el.textContent.trim() === {json.dumps(text)})
            : all.find(el => el.textContent.trim().toLowerCase().includes({json.dumps(text.lower())}));
        if (!target || target.offsetWidth <= 0) return false;
        target.scrollIntoView({{block: 'center', behavior: 'instant'}});
        target.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true, view: window}}));
        target.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true, view: window}}));
        target.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
        return true;
    }}""")

def wait_and_click(page, text, retries=10, interval=2000, use_js=False):
    """Wait for a button with text to appear and click it (prefers native click)."""
    for i in range(retries):
        if use_js:
            if click_js(page, text):
                return True
        else:
            if click_by_text(page, text):
                return True
        page.wait_for_timeout(interval)
    return False

def scroll_and_click(page, selector):
    """Scroll element into view and click via Playwright."""
    try:
        loc = page.locator(selector).first
        loc.scroll_into_view_if_needed(timeout=5000)
        page.wait_for_timeout(300)
        loc.click(timeout=5000)
        return True
    except Exception:
        return False

# ── OTP ──────────────────────────────────────────────────────────────────────

def extract_code(text):
    if not text: return None
    m = re.search(r"[Vv]erification\s*[Cc]ode:?\s*(\d{6})", text)
    if m: return m.group(1)
    m = re.search(r"\b(\d{6})\b", text)
    if m: return m.group(1)
    return None

# Backward-compat alias for test files
extract_verification_code = extract_code
safe_print = sp

def poll_otp(target_email, timeout=240):
    if not MAIL_OK:
        sp("    [!] mail_reader not available — can't auto-OTP")
        return None
    sp(f"    [*] Polling OTP for {target_email} (timeout={timeout}s)...")
    start = time.time()
    seen = set()
    while time.time() - start < timeout:
        try:
            for mail in (fetch_emails(unread_only=True, limit=10, mark_as_read=False) or []):
                uid = mail["uid"]
                if uid in seen: continue
                seen.add(uid)
                subj = (mail.get("subject","") or "").lower()
                to = (mail.get("to","") or "").lower()
                target_lower = target_email.lower()
                if target_lower in to and any(w in subj for w in ["verify","builder","aws","otp","code"]):
                    body = (mail.get("body_text","") or mail.get("body_html","") or "")
                    code = extract_code(body)
                    if code:
                        sp(f"    [+] OTP found: {code}")
                        try: mark_email_read(uid)
                        except: pass
                        return code
        except Exception as e:
            sp(f"    [!] OTP poll error: {e}")
        time.sleep(3)
    sp("    [!] OTP timeout")
    return None

# ── URL state detection ──────────────────────────────────────────────────────

def detect_state(page):
    url = page.url
    if not url: return "unknown"
    # Hash fragments from React SPA (profile.aws.amazon.com)
    hash_fragment = page.evaluate("() => window.location.hash || ''")
    full_path = url + hash_fragment

    if "profile.aws.amazon.com" in url:
        body_text = ""
        try:
            body_text = page.evaluate("() => document.body?.innerText?.substring(0, 1000) || ''")
        except Exception:
            pass
        # Check for error states first
        if any(w in body_text.lower() for w in ["err-837", "error processing", "something went wrong", "we couldn't", "problem"]):
            return "error"
        # Check for name page: even if hash says "signup/start" or "enter-email",
        # if there's a visible name input (no @ in placeholder) and no email input, it's name page
        if "signup" in full_path or "start" in full_path or "enter-email" in full_path:
            name_page = page.evaluate("""() => {
                let hasEmail = false, hasName = false;
                for (const i of document.querySelectorAll('input:not([type="hidden"])')) {
                    if (i.offsetWidth <= 0) continue;
                    if (i.type === 'email' || (i.placeholder || '').includes('@')) { hasEmail = true; continue; }
                    if (i.type === 'password') continue;
                    if (i.type === 'checkbox' || i.type === 'radio') continue;
                    if (i.type === 'text' && !(i.placeholder || '').includes('@')) hasName = true;
                }
                return hasName && !hasEmail;
            }""")
            if name_page:
                return "name-page"
        if "verify-otp" in full_path or "verifyotp" in full_path:
            return "verify-otp"
        if "password" in full_path or "set-password" in full_path:
            return "password"
        return "signup-start"
    if "signup/start" in url or "signup-start" in url: return "signup-start"
    if "enter-email" in url: return "enter-email"
    if "verify-otp" in url or "verifyotp" in url: return "verify-otp"
    if "set-password" in url or "password" in url or "create-password" in url: return "password"
    if "signin.aws" in full_path:
        body = ""
        try:
            body = page.evaluate("() => document.body ? document.body.innerText.substring(0, 500) : ''")
        except Exception:
            pass
        if "it's not you" in body.lower() or "try again" in body.lower() or "error" in body.lower():
            return "error"
        return "signin"
    if "error" in url: return "error"
    # Heuristic look
    body_text2 = ""
    try:
        body_text2 = page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''")
    except Exception:
        pass
    if any(w in body_text2.lower() for w in ["err-837", "error processing", "something went wrong"]):
        return "error"
    has_pw = page.evaluate("() => !!document.querySelector('input[type=\"password\"]')")
    if has_pw: return "password"
    has_otp = page.evaluate("""() => {
        const a = document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"])');
        for (const e of a) {
            const p = (e.placeholder || '').toLowerCase();
            if ((p.includes('code') || p.includes('digit') || p.includes('otp')) && e.offsetWidth > 0) return true;
        } return false;
    }""")
    if has_otp: return "verify-otp"
    return "unknown"

# ── Main Account Creation ────────────────────────────────────────────────────

def create_account(page, domain):
    """Full AWS Builder ID account creation via Kiro sign-in."""
    name = gen_name()
    email = gen_email(name, domain)
    password = gen_password()

    sp(f"  [INFO] Name:     {name}")
    sp(f"  [INFO] Email:    {email}")
    sp(f"  [INFO] Password: {password}")

    # 1. Start callback server, register OIDC client, go to Kiro with PKCE params
    _start_callback_server()
    if not _register_oidc_client():
        sp("  [!] OIDC registration failed, falling back to direct signin")
        page.goto(KIRO_SIGNIN, wait_until="domcontentloaded")
        page.wait_for_timeout(800)
    else:
        page.goto(_oidc_client["signin_url"], wait_until="domcontentloaded")
        page.wait_for_timeout(800)

    # Accept cookie banner if visible
    click_by_text(page, "Accept", timeout=3000)

    # Click AWS Builder ID — use JS dispatchEvent because Playwright's
    # native click hangs when the button triggers a full-page redirect
    # to signin.aws.amazon.com.
    bid_clicked = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const target = btns.find(b => b.textContent.includes('Builder ID') && b.offsetWidth > 0);
        if (!target) return false;
        target.scrollIntoView({block: 'center', behavior: 'instant'});
        target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        return true;
    }""")
    if not bid_clicked:
        raise Exception("Could not click AWS Builder ID button")
    sp("  [+] Clicked AWS Builder ID (dispatchEvent)")

    # Wait for Kiro callback
    sp("  [*] Waiting for Kiro callback...")
    for _ in range(15):
        page.wait_for_timeout(2000)
        if _callback_server["signin_params"]:
            sp(f"  [+] Signin callback received")
            break

    if _callback_server["signin_params"]:
        if _navigate_to_oidc_authorize(page):
            sp("  [+] Navigated to OIDC authorize page")
        else:
            sp("  [!] OIDC authorize navigation failed")

    # Wait for AWS form to appear
    for _ in range(30):
        page.wait_for_timeout(3000)
        has_aws = page.evaluate("""() => {
            const doc = document;
            for (const inp of doc.querySelectorAll('input[type="email"]')) {
                if (inp.offsetWidth > 0) return 'email_found';
            }
            if (doc.title && doc.title.includes('Amazon Web Services')) return 'aws_title';
            const txt = (doc.body ? doc.body.innerText : '');
            if (txt.includes('Continue with Google') || txt.includes('Get started')) return 'aws_content';
            if (location.href.includes('signin.aws') || location.href.includes('amazonaws.com')) return 'url';
            return false;
        }""")
        if has_aws:
            sp(f"  [+] AWS page detected ({has_aws})")
            break
        sp(f"  [*] Waiting for AWS page... ({page.url[:80]})")
    else:
        # Retry OIDC authorize if we have params
        if _callback_server["signin_params"] and _oidc_client["client_id"]:
            sp("  [*] Retrying OIDC authorize navigation...")
            _navigate_to_oidc_authorize(page)
            for _ in range(15):
                page.wait_for_timeout(3000)
                has_aws = page.evaluate("""() => {
                    const doc = document;
                    for (const inp of doc.querySelectorAll('input[type="email"]')) {
                        if (inp.offsetWidth > 0) return 'email_found';
                    }
                    if (doc.title && doc.title.includes('Amazon Web Services')) return 'aws_title';
                    if (location.href.includes('signin.aws') || location.href.includes('amazonaws.com')) return 'url';
                    return false;
                }""")
                if has_aws:
                    sp(f"  [+] AWS page detected on retry ({has_aws})")
                    break
            else:
                raise Exception("AWS page did not load (OIDC authorize failed)")
        else:
            raise Exception("AWS page did not load")

    page.wait_for_timeout(1000)
    sp(f"  [+] Redirected to AWS: {page.url[:100]}")

    # Handle AWS cookie consent banner (appears after redirect)
    try:
        aws_accept = page.locator('button[data-id="awsccc-cb-btn-accept"]')
        if aws_accept.is_visible(timeout=5000):
            aws_accept.click(timeout=3000)
            sp("  [+] AWS cookie consent accepted")
            page.wait_for_timeout(2000)
    except Exception:
        try:
            click_by_text(page, "Accept", timeout=3000)
            page.wait_for_timeout(2000)
        except Exception:
            pass

    # 2. Wait for AWS email input to render (React SPA)
    page.wait_for_load_state("load", timeout=30000)
    page.wait_for_timeout(random.randint(3000, 5000))

    # Fill email — try multiple strategies (exclude disabled/checkbox inputs)
    filled = fill_field(page, "input[type='email']:not([disabled])", email)
    if not filled:
        filled = fill_field_js(page, "input[type='email']:not([disabled])", email)
    if not filled:
        filled = page.evaluate(f"""() => {{
            const inputs = document.querySelectorAll('input');
            for (const el of inputs) {{
                if (el.offsetWidth <= 0 || el.offsetHeight <= 0 || el.disabled) continue;
                if (el.type === 'email') {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, {json.dumps(email)});
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
            }}
            // Fallback: check for placeholder with @
            for (const el of inputs) {{
                if (el.offsetWidth <= 0 || el.offsetHeight <= 0 || el.disabled) continue;
                if (el.type === 'checkbox' || el.type === 'radio' || el.type === 'hidden') continue;
                if ((el.placeholder||'').includes('@')) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, {json.dumps(email)});
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
            }}
            return false;
        }}""")
    if not filled:
        try:
            page.locator('input[type="email"]').first.click(timeout=2000)
            page.locator('input[type="email"]').first.fill(email)
            filled = True
        except:
            pass
    if not filled:
        raise Exception("Email input not found/not fillable")
    sp(f"  [+] Email filled: {email}")
    page.wait_for_timeout(400)

    # Robust Submit — try data-testid first (AWS uses [data-testid="test-primary-button"]), then text, then JS, then Enter
    submitted = False
    for method in ["testid", "text", "js", "fallback"]:
        if method == "testid":
            try:
                btn = page.locator('[data-testid="test-primary-button"]').first
                if btn.is_visible(timeout=3000):
                    btn.click(timeout=5000)
                    submitted = True
                    sp("  [+] Continue submitted via data-testid")
            except Exception:
                pass
        elif method == "text":
            if click_by_text(page, "Continue", timeout=5000):
                submitted = True
            elif click_by_text(page, "Next", timeout=3000):
                submitted = True
        elif method == "js" and not submitted:
            try:
                submitted = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const target = btns.find(b => (b.textContent.includes('Continue') || b.textContent.includes('Next')) && b.offsetWidth > 0);
                    if (target) { target.click(); return true; }
                    return false;
                }""")
            except: pass
        elif method == "fallback" and not submitted:
            try:
                page.keyboard.press("Enter")
                submitted = True
            except: pass
        if submitted:
            sp(f"  [+] Continue submitted via {method}")
            break
    if not submitted:
        sp("  [!] WARNING: Could not submit email form")
    page.wait_for_timeout(3000)

    # Wait for redirect to profile.aws.amazon.com
    for _ in range(15):
        if "profile.aws.amazon.com" in page.url:
            break
        page.wait_for_timeout(3000)
        try:
            page.locator('button[type="submit"]').filter(has_text="Continue").first.click(timeout=3000)
        except Exception:
            pass
    page.wait_for_load_state("domcontentloaded", timeout=15000)
    page.wait_for_timeout(400)

    if "profile.aws.amazon.com" not in page.url:
        sp(f"  [!] Not on AWS profile page — URL: {page.url[:120]}")

    # IMPORTANT: Wait for React SPA to render fully (up to 20 seconds)
    page.wait_for_load_state("domcontentloaded", timeout=15000)
    page.wait_for_timeout(2000)
    # Wait for SPA content to actually appear (not just blank page)
    for spa_wait in range(10):
        body_text = (page.evaluate("() => document.body?.innerText?.trim() || ''") or "")
        if len(body_text) > 50:
            sp(f"  [+] SPA content rendered ({len(body_text)} chars)")
            break
        sp(f"  [*] Waiting for SPA to render... ({spa_wait*2}s)")
        page.wait_for_timeout(2000)
    # Check JS is loaded
    has_js = page.evaluate("() => document.body && !document.body.innerText.includes('enable JavaScript')")
    if not has_js:
        sp("  [!] JS not loaded, reloading...")
        page.reload(wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)

    # 3. State-driven flow through signup steps
    for attempt in range(20):
        state = detect_state(page)
        sp(f"  [*] State #{attempt}: {state}")

        if state == "signup-start":
            page.wait_for_timeout(3000)

            body_text = (page.evaluate("() => document.body ? document.body.innerText : ''") or "")
            if "enable JavaScript" in body_text:
                sp("  [!] JS not loaded -- reloading...")
                page.reload(wait_until="load")
                page.wait_for_timeout(8000)
                continue
            if "it's not you" in body_text.lower() or "try again" in body_text.lower():
                raise Exception("AWS proxy blocked -- retry with different country")

            # STEP 0: CCBA cookie consent overlay — check FIRST (may block name input)
            ccba_visible = page.evaluate("""() => {
                const radios = document.querySelectorAll('input[name="awsccc-u-rg-ccba-allowed"]');
                if (!radios.length) return false;
                for (const r of radios) {
                    const rect = r.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) return true;
                }
                return false;
            }""")
            if ccba_visible:
                sp("  [+] CCBA visible -- accepting...")
                page.evaluate("""() => {
                    let t = document.querySelector('input[name="awsccc-u-rg-ccba-allowed"][value="yes"]');
                    if (!t) t = document.querySelectorAll('input[name="awsccc-u-rg-ccba-allowed"]')[0];
                    if (!t) return;
                    t.scrollIntoView({block:'center'});
                    t.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    t.dispatchEvent(new Event('change', {bubbles: true}));
                }""")
                page.wait_for_timeout(1000)
                wait_and_click(page, "Accept", retries=3, interval=1000) or click_js(page, "Accept")
                sp("  [+] CCBA: Accept clicked")
                page.wait_for_timeout(2000)
                continue

            # STEP 1: Look for name input (placeholder varies by locale)
            name_input = None
            for sel in [
                'input[autocomplete="given-name"]',
                'input[autocomplete="name"]',
                'input[placeholder*="name" i]',
                'input[name*="name" i]',
                '#fullName', '#name', '#displayName',
                '#firstName', '#lastName',
            ]:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=500):
                        name_input = loc
                        break
                except:
                    pass
            if not name_input:
                # JS-based: find first visible non-email/non-password/non-checkbox text input
                found = page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                    for (const inp of inputs) {
                        if (inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled) {
                            const id = (inp.id || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            if (id.includes('awsccc') || nm.includes('awsccc')) continue;
                            return inp.id ? '#' + CSS.escape(inp.id) : '';
                        }
                    }
                    return null;
                }""")
                if found:
                    try:
                        name_input = page.locator(found).first
                    except:
                        pass
            if not name_input:
                for inp in page.locator('input').all():
                    t = inp.get_attribute('type') or ''
                    if t in ('hidden','checkbox','radio','email','password'): continue
                    if inp.is_visible(timeout=300):
                        # Skip awsccc cookie inputs
                        inp_id = (inp.get_attribute('id') or '').lower()
                        inp_name = (inp.get_attribute('name') or '').lower()
                        if 'awsccc' in inp_id or 'awsccc' in inp_name: continue
                        name_input = inp
                        break

            if name_input:
                name_input.click(timeout=3000)
                page.wait_for_timeout(300)
                name_input.fill(name)
                page.evaluate("() => document.activeElement && document.activeElement.blur()")
                page.wait_for_timeout(500)
                sp(f"  [+] Name: {name}")

                # Robust Continue submit — try data-testid first
                name_submitted = False
                for method in ["testid", "text", "fallback"]:
                    if method == "testid":
                        try:
                            btn = page.locator('[data-testid="test-primary-button"]').first
                            if btn.is_visible(timeout=3000):
                                btn.click(timeout=5000)
                                name_submitted = True
                                sp("  [+] Continue submitted via data-testid")
                        except: pass
                    elif method == "text":
                        for btn_text in ['Continue', 'Continuer', 'Continuar', 'Next']:
                            try:
                                if page.locator(f'button[type="submit"]:has-text("{btn_text}")').first.is_visible(timeout=1000):
                                    page.locator(f'button[type="submit"]:has-text("{btn_text}")').first.click(timeout=5000)
                                    name_submitted = True
                                    break
                            except: continue
                        if not name_submitted:
                            name_submitted = wait_and_click(page, "Continue", retries=3, interval=1500)
                    elif method == "fallback" and not name_submitted:
                        try:
                            page.keyboard.press("Enter")
                            name_submitted = True
                        except: pass
                    if name_submitted:
                        sp(f"  [+] Continue (name) submitted via {method}")
                        break
                if not name_submitted:
                    sp("  [!] WARNING: Could not submit name form")
                page.wait_for_timeout(2000)
                continue

            # STEP 3: Nothing found
            sp("  [-] No name or CCBA -- waiting")
            page.wait_for_timeout(5000)

        elif state == "name-page":
            # Detect state correctly identified name page (even though hash says enter-email)
            sp("  [*] Name page detected via content analysis")
            page.wait_for_timeout(2000)
            try:
                # Find name input
                name_input = None
                found = page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                    for (const inp of inputs) {
                        if (inp.offsetWidth > 0 && inp.type === 'text' && !(inp.placeholder || '').includes('@')) {
                            const id = (inp.id || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            if (id.includes('awsccc') || nm.includes('awsccc')) continue;
                            return inp.id ? '#' + CSS.escape(inp.id) : '';
                        }
                    }
                    return null;
                }""")
                if found:
                    name_input = page.locator(found).first
                if not name_input:
                    # Fallback: find any visible text input without @ in placeholder
                    for inp in page.locator('input').all():
                        t = inp.get_attribute('type') or ''
                        if t in ('hidden','checkbox','radio','email','password'): continue
                        if inp.is_visible(timeout=300):
                            inp_id = (inp.get_attribute('id') or '').lower()
                            inp_name = (inp.get_attribute('name') or '').lower()
                            if 'awsccc' in inp_id or 'awsccc' in inp_name: continue
                            placeholder = inp.get_attribute('placeholder') or ''
                            if '@' not in placeholder:
                                name_input = inp
                                break
                if name_input:
                    name_input.click(timeout=3000)
                    page.wait_for_timeout(300)
                    name_input.fill(name)
                    page.evaluate("() => document.activeElement && document.activeElement.blur()")
                    page.wait_for_timeout(500)
                    sp(f"  [+] Name: {name}")
                    # Robust Continue submit
                    try:
                        btn = page.locator('[data-testid="test-primary-button"]').first
                        if btn.is_visible(timeout=3000):
                            btn.click(timeout=5000)
                            sp("  [+] Continue submitted via data-testid")
                        else:
                            wait_and_click(page, "Continue", retries=3, interval=1500)
                            sp("  [+] Continue (name)")
                    except:
                        wait_and_click(page, "Continue", retries=3, interval=1500)
                        sp("  [+] Continue (name) via fallback")
                    page.wait_for_timeout(3000)
                    continue
            except Exception as e:
                sp(f"  [!] Name-page handler error: {e}")
            page.wait_for_timeout(3000)
            continue

        elif state == "enter-email":
            # Page may be on enter-email view but actually showing name page (SPA transition)
            sp("  [*] Page is on enter-email view, waiting for name page...")
            page.wait_for_timeout(random.randint(5000, 10000))
            # Check if name field is visible on this page
            try:
                has_name = page.evaluate("""() => {
                    for (const i of document.querySelectorAll('input')) {
                        if (i.offsetWidth > 0 && i.type === 'text' && !(i.placeholder||'').includes('@')) return true;
                    }
                    return false;
                }""")
                if has_name:
                    sp("  [*] Name field found on enter-email view, this IS the name page")
                    continue
            except Exception:
                pass
            # If email field is visible, fill and submit
            try:
                has_email = page.evaluate("""() => {
                    for (const i of document.querySelectorAll('input[type="email"]')) {
                        if (i.offsetWidth > 0) return true;
                    }
                    return false;
                }""")
                if has_email:
                    fill_field_js(page, "input[type='email']", email)
                    page.wait_for_timeout(1000)
                    try:
                        btn = page.locator('[data-testid="test-primary-button"]').first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            sp("  [+] Continue (enter-email) via data-testid")
                        else:
                            wait_and_click(page, "Continue")
                            sp("  [+] Continue (enter-email)")
                    except:
                        wait_and_click(page, "Continue")
                        sp("  [+] Continue (enter-email)")
                    page.wait_for_timeout(2500)
            except Exception:
                pass
            continue

        elif state == "verify-otp":
            code = poll_otp(email, timeout=240)
            if code:
                # Fill OTP — AWS uses individual 6-digit fields or one field
                otp_sel = page.evaluate("""() => {
                    const a = document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"])');
                    for (const e of a) {
                        const p = (e.placeholder || '').toLowerCase();
                        if ((p.includes('code') || p.includes('digit') || p.includes('otp')) && e.offsetWidth > 0)
                            return e.id ? '#' + CSS.escape(e.id) : '';
                    } return '';
                }""")
                if otp_sel and fill_field_js(page, otp_sel, code):
                    sp(f"  [+] OTP code filled: {code}")
                    page.wait_for_timeout(1000)
                else:
                    # Try filling each digit into separate fields
                    digit_inputs = page.evaluate("""() => {
                        const a = document.querySelectorAll('input[type="text"]:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])');
                        const visible = [];
                        for (const e of a) {
                            if (e.offsetWidth > 0 && e.maxLength === 1) visible.push(e);
                        } return visible.length;
                    }""")
                    if digit_inputs == 6:
                        for i, d in enumerate(code):
                            fill_field_js(page, f"input[type='text']:nth-of-type({i+1})", d)
                        sp(f"  [+] OTP digits filled")
                        page.wait_for_timeout(500)

                wait_and_click(page, "Continue") or wait_and_click(page, "Verify")
                sp("  [+] OTP submitted")
                page.wait_for_timeout(5000)
            else:
                sp("  [!] No OTP — waiting 30s...")
                page.wait_for_timeout(30000)

        elif state == "password":
            if fill_field(page, "input[type='password']", password) or fill_field_js(page, "input[type='password']", password):
                sp("  [+] Password filled")
                page.wait_for_timeout(1000)

                # Tick any terms/agreement checkboxes (not awsccc cookies)
                try:
                    checked = page.evaluate("""() => {
                        let count = 0;
                        for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                            if (!cb.offsetWidth || !cb.offsetHeight) continue;
                            const id = (cb.id || '').toLowerCase();
                            const name = (cb.name || '').toLowerCase();
                            if (id.includes('awsccc') || name.includes('awsccc')) continue;
                            if (!cb.checked) {
                                cb.click();
                                count++;
                            }
                        }
                        return count;
                    }""")
                    if checked:
                        sp(f"  [+] Ticked {checked} terms/agreement checkbox(es)")
                        page.wait_for_timeout(500)
                except Exception:
                    pass

                # Try multiple button text variants
                clicked = wait_and_click(page, "Create AWS Builder ID") or \
                    wait_and_click(page, "Create") or \
                    wait_and_click(page, "Continue")
                if clicked:
                    sp("  [+] Account created!")
                else:
                    sp("  [!] No Create/Continue button found after password")
                page.wait_for_timeout(3000)
                return name, email, password
            page.wait_for_timeout(3000)

        elif state == "error":
            # ERR-837 or other AWS error — retry with longer wait
            body_text = ""
            try:
                body_text = (page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''") or "")
            except Exception:
                pass
            sp(f"  [!] Error state detected: {body_text[:100]}")
            # Check if we already filled name (ERR-837 after name submit)
            # Try to detect name field and refill
            try:
                has_name = page.evaluate("""() => {
                    for (const i of document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])')) {
                        if (i.offsetWidth > 0 && i.type === 'text' && !(i.placeholder||'').includes('@')) return true;
                    }
                    return false;
                }""")
                if has_name:
                    sp("  [*] ERR-837 after name submit, waiting longer and retrying...")
                    page.wait_for_timeout(random.randint(5000, 10000))
                    # Try to refill name
                    try:
                        page.evaluate("""(n) => {
                            const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                            for (const inp of inputs) {
                                if (inp.offsetWidth > 0 && inp.type === 'text') {
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(inp, n);
                                    inp.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: n}));
                                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                                    return;
                                }
                            }
                        }""", name)
                        sp("  [+] Name refilled, waiting before submit...")
                        page.wait_for_timeout(random.randint(5000, 10000))
                        # Try Continue with data-testid
                        try:
                            page.locator('[data-testid="test-primary-button"]').first.click()
                            sp("  [+] Continue clicked (retry)")
                        except:
                            click_by_text(page, "Continue", timeout=5000)
                            sp("  [+] Continue clicked (retry text)")
                        page.wait_for_timeout(random.randint(5000, 10000))
                    except Exception as e:
                        sp(f"  [!] Retry error: {e}")
                else:
                    sp("  [*] Error before name fill, waiting...")
                    page.wait_for_timeout(10000)
            except Exception:
                page.wait_for_timeout(5000)
            continue

        elif state == "unknown":
            # Wait for React to render
            page.wait_for_timeout(3000)
            # Check if we need to sign in first (account already exists)
            if "signin.aws" in page.url:
                sp("  [*] On signin page — filling credentials...")
                if fill_field_js(page, "input[type='email']", email):
                    page.wait_for_timeout(1500)
                    wait_and_click(page, "Next") or wait_and_click(page, "Continue")
                    page.wait_for_timeout(5000)
                    if fill_field_js(page, "input[type='password']", password):
                        page.wait_for_timeout(1000)
                        wait_and_click(page, "Sign in")
                        page.wait_for_timeout(8000)

            if attempt > 20:
                sp("  [!] Too many unknown state iterations — aborting")
                break

        page.wait_for_timeout(2000)

    sp("  [!] Account creation did not fully complete")
    raise Exception("Account creation incomplete")

# ── Panel Login ──────────────────────────────────────────────────────────────

def panel_login(page, panel_url, panel_pass):
    """Login to 9Router panel via API."""
    sp("  [*] Logging into panel...")
    page.goto(panel_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    result = page.evaluate(f"""async () => {{
        try {{
            const r = await fetch('/api/auth/login', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{password: {json.dumps(panel_pass)}}})
            }});
            return {{ok: r.ok, data: await r.text()}};
        }} catch(e) {{ return {{ok: false, error: e.message}}; }}
    }}""")
    if result.get("ok"):
        sp("  [+] Panel API login succeeded")
        page.goto(panel_url)
        page.wait_for_timeout(2000)
        return True
    sp(f"  [!] Panel login failed: {result.get('data', result.get('error', ''))[:200]}")
    return False

# ── Add Account to Panel ─────────────────────────────────────────────────────

def add_to_panel(page, kiro_email, kiro_password, panel_url):
    """Add a Kiro account to 9Router panel via device authorization flow.

    Uses Playwright native clicks (React-safe) to interact with the panel UI,
    then opens the AWS device URL in a separate context for OAuth authorization.
    """
    sp("  [*] Adding account to Kiro provider...")

    page.goto(f"{panel_url}/dashboard/providers/kiro", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # Click Add button — try Playwright native first
    add_clicked = False
    try:
        add_btn = page.locator("button").filter(has_text="addAdd").or_(
            page.locator("button").filter(has_text="Add")
        ).first
        if add_btn.is_visible(timeout=3000):
            add_btn.click(timeout=5000)
            add_clicked = True
            sp("  [+] Clicked Add (native)")
    except Exception:
        pass

    if not add_clicked:
        # Fallback: use text matching with whitespace normalization
        add_clicked = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const t = (b.textContent || "").trim().replace(/[\\s\\u00A0]/g, '');
                if ((t === 'addAdd' || t.includes('Add')) && b.offsetWidth > 0) {
                    b.scrollIntoView({block:'center'});
                    b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    return true;
                }
            } return false;
        }""")
        if add_clicked:
            sp("  [+] Clicked Add (JS fallback)")
    page.wait_for_timeout(2000)

    # Click AWS Builder ID option in the dialog
    aws_clicked = False
    try:
        aws_btn = page.locator("button").filter(has_text="AWS Builder ID").first
        if aws_btn.is_visible(timeout=3000):
            aws_btn.click(timeout=5000)
            aws_clicked = True
            sp("  [+] Clicked AWS Builder ID (native)")
    except Exception:
        pass

    if not aws_clicked:
        aws_clicked = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const t = (b.textContent || "").trim();
                if (t.includes("AWS Builder ID") && b.offsetWidth > 0) {
                    b.scrollIntoView({block:'center'});
                    b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    return true;
                }
            } return false;
        }""")
        if aws_clicked:
            sp("  [+] Clicked AWS Builder ID (JS)")

    # Wait for device code to load from API
    sp("  [*] Waiting for device authorization code...")
    device_url = None
    user_code = None

    for _ in range(30):
        page.wait_for_timeout(1000)
        # Try multiple overlay/dialog selectors
        diag_text = page.evaluate("""() => {
            const selectors = [
                '.fixed.inset-0',
                '[role="dialog"]',
                '.modal',
                '.dialog',
                '[class*="dialog"]',
                '[class*="modal"]',
                '[class*="overlay"]',
            ];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const o of els) {
                    if (o.offsetWidth > 0 && o.innerText.length > 20) return o.innerText;
                }
            }
            // Fallback: grab all text from body that mentions awsapps
            const body = document.body.innerText || '';
            const m = body.match(/https:\\/\\/view\\.awsapps\\.com[^\\s]*/);
            return m ? m[0] : '';
        }""")
        m = re.search(r'https://view\.awsapps\.com[^\s]*', diag_text)
        if m:
            device_url = m.group(0)
            cm = re.search(r'Your Code\s*\n?\s*([A-Z0-9-]+)', diag_text)
            if cm: user_code = cm.group(1)
            sp(f"  [+] Device URL: {device_url}")
            if user_code: sp(f"  [+] User Code: {user_code}")
            break
        # Also check if the page body itself contains the URL (some panels render it inline)
        body_check = page.evaluate("""() => {
            const txt = document.body?.innerText || '';
            const m = txt.match(/https:\\/\\/view\\.awsapps\\.com[^\\s]*/);
            return m ? m[0] : '';
        }""")
        if body_check and not device_url:
            device_url = body_check
            sp(f"  [+] Device URL (from body): {device_url}")
            break

    if not device_url:
        sp("  [!] Could not get device URL — dialog content:")
        diag = page.evaluate("""() => {
            const os = document.querySelectorAll('.fixed.inset-0');
            for (const o of os) {
                if (o.offsetWidth > 0) return o.innerText.substring(0, 500);
            } return 'no dialog';
        }""")
        sp(f"  Dialog: {diag}")
        # Try approaching with direct API call
        sp("  [*] Trying direct API for device code...")
        dc = page.evaluate(f"""async () => {{
            try {{
                const r = await fetch('/api/oauth/kiro/device-code', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{provider: 'kiro', type: 'aws-builder-id'}})
                }});
                return {{ok: r.ok, data: await r.text()}};
            }} catch(e) {{ return {{ok: false, error: e.message}}; }}
        }}""")
        if dc.get("ok"):
            sp(f"  [+] Direct API response: {str(dc['data'])[:300]}")
        return False

    # Open device URL in a fresh browser context
    sp("  [*] Opening device URL for sign-in...")
    auth_ctx = page.context.browser.new_context()
    auth_page = auth_ctx.new_page()
    auth_page.set_default_timeout(30000)

    try:
        auth_page.goto(device_url, wait_until="domcontentloaded", timeout=30000)
        auth_page.wait_for_timeout(5000)
        sp(f"  Device URL after load: {auth_page.url[:120]}")

        # Check for error
        body_text = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
        if "unable" in body_text.lower() and "error" in body_text.lower():
            sp(f"  [!] AWS error on device page: {body_text[:300]}")
            auth_ctx.close()
            return False

        # Wait for sign-in form
        for step in range(12):
            if auth_page.evaluate("() => !!document.querySelector('input[type=\"email\"]')"):
                break
            auth_page.wait_for_timeout(3000)
            sp(f"  Waiting for email input... ({step+1}/12)")

        # Fill email
        if fill_field_js(auth_page, "input[type='email']", kiro_email):
            sp(f"  [+] Email filled (device): {kiro_email}")
        auth_page.wait_for_timeout(1500)

        # Click Continue
        wait_and_click(auth_page, "Continue", retries=5, interval=2000)
        sp("  [+] Continue (device email)")
        auth_page.wait_for_timeout(8000)

        # Wait for password input
        pw_done = False
        for _ in range(20):
            if auth_page.evaluate("() => !!document.querySelector('input[type=\"password\"]')"):
                break
            auth_page.wait_for_timeout(3000)
        else:
            sp(f"  [!] No password field found. URL: {auth_page.url[:100]}")

        if fill_field_js(auth_page, "input[type='password']", kiro_password):
            sp("  [+] Password filled (device)")
            auth_page.wait_for_timeout(1500)

        # Click Sign in
        wait_and_click(auth_page, "Sign in") or wait_and_click(auth_page, "sign-in") or wait_and_click(auth_page, "Submit")
        sp("  [+] Sign in clicked (device)")
        auth_page.wait_for_timeout(10000)
        sp(f"  URL after sign-in: {auth_page.url[:120]}")

        # Click Allow / Authorize if present
        for _ in range(10):
            allow_text = auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = b.textContent.trim().toLowerCase();
                    if ((t.includes('allow') || t.includes('authorize')) && b.offsetWidth > 0) {
                        b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                        return b.textContent.trim();
                    }
                } return '';
            }""")
            if allow_text:
                sp(f"  [+] Clicked: {allow_text}")
                auth_page.wait_for_timeout(5000)
                break
            auth_page.wait_for_timeout(2000)

        # Wait for panel to detect authorization
        sp("  [*] Waiting for panel to detect authorization...")
        auth_detected = False
        for _ in range(30):
            page.wait_for_timeout(2000)
            diag_after = page.evaluate("""() => {
                const os = document.querySelectorAll('.fixed.inset-0');
                for (const o of os) {
                    if (o.offsetWidth > 0) return o.innerText.substring(0, 300);
                } return '';
            }""")
            if not diag_after:
                sp("  [+] Dialog closed — authorization detected!")
                auth_detected = True
                break
            if any(w in diag_after.lower() for w in ['success', 'connected', 'authorized']):
                sp(f"  [+] {diag_after[:200]}")
                auth_detected = True
                break

        auth_ctx.close()
        return auth_detected

    except Exception as e:
        sp(f"  [!] Device auth error: {e}")
        try: auth_ctx.close()
        except: pass
        return False

# ── Save ─────────────────────────────────────────────────────────────────────

def save_creds(email, password, panel_url, name=""):
    file_exists = CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["Name", "Email", "Password", "Panel", "Timestamp"])
        w.writerow([name, email, password, panel_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    sp(f"  [+] Saved to {CSV_FILE}")

# ── Main CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Kiro Builder ID Account Creator")
    ap.add_argument("--panel", "-p", help="Panel URL")
    ap.add_argument("--password", "-w", help="Panel password")
    ap.add_argument("--interval", "-i", default="3m", help="Interval between accounts (e.g. 3m, 5m)")
    ap.add_argument("--domain", "-d", default="havenhaus.in", help="Email domain")
    ap.add_argument("--country", "-c", default="us", help="Proxy country")
    ap.add_argument("--headless", action="store_true", help="Headless mode")
    ap.add_argument("--visible", action="store_true", help="Visible browser")
    ap.add_argument("--once", action="store_true", help="Run once then exit")
    args = ap.parse_args()

    sp("=" * 60)
    sp("  Kiro Builder ID — Full Automation")
    sp("  Camoufox + Residential Proxy + Gmail OTP")
    sp("=" * 60)
    sp()

    panel_url = args.panel or input("  Panel URL: ").strip()
    panel_pass = args.password or input("  Panel Password: ").strip()
    interval = parse_interval(args.interval or "3m")
    domain = args.domain or "havenhaus.in"
    country = args.country or "us"
    headless = args.headless if args.headless else (not args.visible)

    sp(f"  Panel:     {panel_url}")
    sp(f"  Interval:  {fmt_time(interval)}")
    sp(f"  Domain:    @{domain}")
    sp(f"  Country:   {country.upper()}")
    sp(f"  Headless:  {headless}")
    sp()

    if not args.once:
        input("  Press Enter to start... ")

    run = 0
    while True:
        run += 1
        sp(f"\n{'=' * 60}")
        sp(f"  RUN #{run}")
        sp(f"{'=' * 60}")

        proxy = get_proxy(country)

        try:
            with Camoufox(
                geoip=True,
                proxy=proxy,
                humanize=True,
                headless=headless,
                os="windows",
            ) as browser:
                page = browser.new_page()
                page.set_default_timeout(30000)

                # Check IP
                try:
                    page.goto("https://httpbin.org/ip", timeout=15000)
                    page.wait_for_timeout(2000)
                    ip = page.locator("body").text_content() or ""
                    sp(f"  [*] IP: {ip.strip()}")
                except:
                    sp("  [*] IP check unavailable")

                # Step 1: Create account
                sp("\n  --- Creating Kiro Builder ID Account ---")
                name, kiro_email, kiro_password = create_account(page, domain)

                # Step 2: Panel login
                sp("\n  --- Panel Login ---")
                panel_login(page, panel_url, panel_pass)

                # Step 3: Add to panel
                sp("\n  --- Adding to Kiro Provider ---")
                added = add_to_panel(page, kiro_email, kiro_password, panel_url)

                if added:
                    save_creds(kiro_email, kiro_password, panel_url, name)
                    sp("\n  [DONE] Account created and added to panel!")
                else:
                    sp("\n  [!] Account created but panel add may have failed")
                    save_creds(kiro_email, kiro_password, panel_url, name + " (panel-pending)")

                # Cleanup
                try: page.context.clear_cookies()
                except: pass

        except Exception as e:
            sp(f"\n  [ERROR] {e}")
            import traceback
            traceback.print_exc()

        if args.once:
            break

        sp(f"\n  [*] Next run in {fmt_time(interval)}...")
        remaining = interval
        while remaining > 0:
            try:
                sys.stdout.write(f"\r  Next: {fmt_time(remaining)}      ")
                sys.stdout.flush()
            except OSError:
                pass
            time.sleep(min(5, remaining))
            remaining -= 5
        sp()

    sp("\n  Done!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sp("\n  Stopped.")
        sys.exit(0)
