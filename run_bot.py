#!/usr/bin/env python3
"""
Kiro Builder ID — Self-Improving Anti-Ban Account Creator
===========================================================
Camoufox-native · SQLite learning DB · Config rotation · Auto-recovery
Organic navigation · Native APIs · Fresh profiles

Usage:
    set PROXYRISE_SERVER=http://your-proxy:port
    set PROXYRISE_KEY=your-api-key
    python run_bot.py --panel http://localhost:20128 --password 741085209630
    python run_bot.py --once --headless
"""
import argparse, base64, csv, hashlib, json, os, random, re, secrets, shutil, socket, sqlite3, string, sys, tempfile, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

# Panel drivers (modular, universal)
sys.path.insert(0, str(Path(__file__).parent))
try:
    from panel_drivers import get_driver as _get_panel_driver
    PANEL_DRIVERS_OK = True
except Exception:
    PANEL_DRIVERS_OK = False

# ── Conditional imports ──────────────────────────────────────────────────────
try:
    from camoufox.sync_api import Camoufox
    CAMOUFOX_OK = True
except ImportError:
    Camoufox = None
    CAMOUFOX_OK = False

import logging as _lg
for _n in ['gmail_oauth', 'mail_reader', 'google.auth', 'google_auth_oauthlib']:
    _l = _lg.getLogger(_n)
    _l.setLevel(_lg.CRITICAL); _l.handlers.clear(); _l.propagate = False

# Mail-provider abstraction (disposable email)
MAIL_PROVIDER_DIR = Path(__file__).parent / 'mail_providers'
if str(MAIL_PROVIDER_DIR) not in sys.path:
    sys.path.insert(0, str(MAIL_PROVIDER_DIR.parent))
try:
    from mail_providers import get_provider, list_providers
    MAIL_PROVIDERS_OK = True
except Exception:
    MAIL_PROVIDERS_OK = False

# Faker for localized fake identities
try:
    from faker import Faker
    FAKER_OK = True
except ImportError:
    FAKER_OK = False

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent / 'automation' / 'automation'
CLOAKBROWSER_DIR = Path(__file__).parent / 'CloakBrowser'
for _p in [str(CLOAKBROWSER_DIR), str(BASE_DIR.parent), str(BASE_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Docker: write CSV/screenshots to mounted /app/output/ if it exists
_output_dir = Path(os.environ.get('OUTPUT_DIR', ''))
if not _output_dir or not _output_dir.exists():
    _output_dir = BASE_DIR
CSV_FILE = _output_dir / 'kiro_accounts.csv'
DB_FILE = BASE_DIR / 'learning.db'
SCREENSHOT_DIR = _output_dir / 'screenshots'
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# ── Proxy config — Proxyrise Residential (env-configurable) ──────────────────
PROXY_PROVIDERS = {
    'residential': {
        'server': os.environ.get('PROXYRISE_SERVER'),
        'key': os.environ.get('PROXYRISE_KEY'),
        'format': 'res-{country}',
        'countries': ['us', 'gb', 'de', 'ca', 'au', 'fr', 'nl', 'se', 'no', 'dk', 'any']
    },
}

# Cloudflare/datacenter IP prefixes to reject
DATACENTER_ORGS = ("cloudflare", "amazon", "google", "microsoft", "digitalocean", "ovh", "hetzner")

# Available proxy countries
PROXY_COUNTRIES = ['us', 'gb', 'de', 'ca', 'au', 'fr', 'nl', 'se', 'no', 'dk', 'za']

# ── Viewport presets (real monitor sizes per OS) ─────────────────────────────
VIEWPORTS = {
    'windows': [
        {'width': 1366, 'height': 768}, {'width': 1920, 'height': 1080},
        {'width': 1536, 'height': 864}, {'width': 1280, 'height': 720},
        {'width': 1440, 'height': 900}, {'width': 1600, 'height': 900},
        {'width': 1360, 'height': 768},
    ],
    'macos': [
        {'width': 1440, 'height': 900}, {'width': 1680, 'height': 1050},
        {'width': 1280, 'height': 800}, {'width': 2560, 'height': 1600},
        {'width': 1920, 'height': 1200},
    ],
    'linux': [
        {'width': 1920, 'height': 1080}, {'width': 1366, 'height': 768},
        {'width': 1280, 'height': 1024}, {'width': 1680, 'height': 1050},
        {'width': 2560, 'height': 1440},
    ],
}

# ── Locale/timezone mapping per proxy country ──────────────────────────────
COUNTRY_LOCALE = {
    'us': {'locale': 'en-US', 'tz': 'America/New_York'},
    'gb': {'locale': 'en-GB', 'tz': 'Europe/London'},
    'de': {'locale': 'de-DE', 'tz': 'Europe/Berlin'},
    'ca': {'locale': 'en-CA', 'tz': 'America/Toronto'},
    'au': {'locale': 'en-AU', 'tz': 'Australia/Sydney'},
    'fr': {'locale': 'fr-FR', 'tz': 'Europe/Paris'},
    'nl': {'locale': 'nl-NL', 'tz': 'Europe/Amsterdam'},
    'se': {'locale': 'sv-SE', 'tz': 'Europe/Stockholm'},
    'no': {'locale': 'nb-NO', 'tz': 'Europe/Oslo'},
    'dk': {'locale': 'da-DK', 'tz': 'Europe/Copenhagen'},
    'za': {'locale': 'en-ZA', 'tz': 'Africa/Johannesburg'},
    'any': {'locale': 'en-US', 'tz': 'America/New_York'},
}

# ── Behavioral profiles ──────────────────────────────────────────────────────
BEHAVIOR_PROFILES = {
    "fast": {"typing_delay": (30, 80), "mouse_steps": (6, 12), "pause_short": (300, 800), "pause_long": (1000, 2000), "w": 20},
    "slow": {"typing_delay": (120, 300), "mouse_steps": (14, 22), "pause_short": (800, 2000), "pause_long": (3000, 6000), "w": 20},
    "variable": {"typing_delay": (40, 250), "mouse_steps": (8, 18), "pause_short": (400, 1500), "pause_long": (1500, 4000), "w": 60},
}
PROFILE_NAMES = list(BEHAVIOR_PROFILES.keys())

STEPS = ["navigate", "click_builder", "fill_email", "fill_name", "wait_otp", "fill_otp",
         "fill_password", "create", "redirect", "explore"]

# ══════════════════════════════════════════════════════════════════════════════
# SQLite LEARNING DATABASE
# ══════════════════════════════════════════════════════════════════════════════

class LearningDB:
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, config_hash TEXT, proxy_ip TEXT,
                proxy_org TEXT, os TEXT, viewport TEXT, preset_idx INTEGER,
                domain TEXT, profile_type TEXT, result TEXT,
                ban_step TEXT, error_text TEXT, duration_sec REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                hash TEXT PRIMARY KEY, os TEXT, viewport_w INTEGER,
                viewport_h INTEGER, locale TEXT, preset_idx INTEGER,
                profile_type TEXT, survival_score INTEGER DEFAULT 0,
                ban_count INTEGER DEFAULT 0, success_count INTEGER DEFAULT 0,
                last_used TEXT, enabled INTEGER DEFAULT 1
            )
        """)
        conn.commit(); conn.close()

    def _hash_config(self, config):
        raw = f"{config['os']}|{config['viewport']['width']}x{config['viewport']['height']}|{config.get('locale','en-US')}|{config['preset_idx']}|{config['profile_type']}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def upsert_config(self, config):
        h = self._hash_config(config)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            INSERT INTO configs (hash, os, viewport_w, viewport_h, locale, preset_idx, profile_type, last_used, enabled)
            VALUES (?,?,?,?,?,?,?,datetime('now'),1)
            ON CONFLICT(hash) DO UPDATE SET last_used=datetime('now')
        """, (h, config['os'], config['viewport']['width'], config['viewport']['height'],
              config.get('locale', 'en-US'), config['preset_idx'], config['profile_type']))
        conn.commit(); conn.close()
        return h

    def record_attempt(self, config_hash, proxy_ip, proxy_org, config, result, ban_step=None, error_text=None, duration_sec=0):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            INSERT INTO attempts (timestamp, config_hash, proxy_ip, proxy_org, os, viewport, preset_idx, domain, profile_type, result, ban_step, error_text, duration_sec)
            VALUES (datetime('now'),?,?,?,?,?,?,?,?,?,?,?,?)
        """, (config_hash, proxy_ip, proxy_org, config['os'],
              f"{config['viewport']['width']}x{config['viewport']['height']}",
              config['preset_idx'], config['domain'], config['profile_type'],
              result, ban_step, (error_text or '')[:200], duration_sec))
        # Update scores
        if result == "survived":
            conn.execute("UPDATE configs SET survival_score = survival_score + 1, success_count = success_count + 1 WHERE hash = ?", (config_hash,))
        elif result in ("banned", "error"):
            conn.execute("UPDATE configs SET survival_score = survival_score - 2, ban_count = ban_count + 1 WHERE hash = ?", (config_hash,))
            # Auto-disable if score too low
            conn.execute("UPDATE configs SET enabled = 0 WHERE hash = ? AND survival_score < -3", (config_hash,))
        conn.commit(); conn.close()

    def get_best_config(self):
        """Get the highest-scoring enabled config, or None."""
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("""
            SELECT hash, os, viewport_w, viewport_h, preset_idx, profile_type, survival_score
            FROM configs WHERE enabled = 1 ORDER BY survival_score DESC, last_used ASC LIMIT 3
        """).fetchall()
        conn.close()
        if row:
            r = random.choice(row)
            return {
                'hash': r[0], 'os': r[1],
                'viewport': {'width': r[2], 'height': r[3]},
                'preset_idx': r[4], 'profile_type': r[5], 'score': r[6],
            }
        return None

    def get_disabled_presets(self):
        """Return set of preset_idxs that are in disabled configs."""
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT DISTINCT preset_idx FROM configs WHERE enabled = 0").fetchall()
        conn.close()
        return {r[0] for r in rows}

    def get_stats(self):
        conn = sqlite3.connect(str(self.db_path))
        total = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        survived = conn.execute("SELECT COUNT(*) FROM attempts WHERE result='survived'").fetchone()[0]
        banned = conn.execute("SELECT COUNT(*) FROM attempts WHERE result='banned'").fetchone()[0]
        errors = conn.execute("SELECT COUNT(*) FROM attempts WHERE result='error'").fetchone()[0]
        active_configs = conn.execute("SELECT COUNT(*) FROM configs WHERE enabled=1").fetchone()[0]
        total_configs = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
        conn.close()
        return {'total': total, 'survived': survived, 'banned': banned, 'errors': errors,
                'active_configs': active_configs, 'total_configs': total_configs}

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG ROTATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def generate_config(db=None, disabled_presets=None):
    """Generate a randomized config. Avoid presets that have been banned before."""
    os_choice = random.choice(['windows', 'macos', 'linux'])
    vp = random.choice(VIEWPORTS.get(os_choice, VIEWPORTS['windows']))
    screen_w = vp['width'] + random.choice([0, 0, 0, 0, random.randint(0, 400)])
    screen_h = vp['height'] + random.choice([0, 0, 0, 0, random.randint(0, 200)])

    if disabled_presets is None:
        disabled_presets = set()
    # 30% chance: try a known-good config from DB
    if db and random.random() < 0.30:
        best = db.get_best_config()
        if best:
            return {
                'os': best['os'],
                'viewport': best['viewport'],
                'preset_idx': best['preset_idx'],
                'profile_type': best['profile_type'],
                'from_db': True,
            }

    # Pick preset avoiding disabled ones
    all_presets = list(range(12))
    available = [p for p in all_presets if p not in disabled_presets]
    if not available:
        available = all_presets

    return {
        'os': os_choice,
        'viewport': vp,
        'preset_idx': random.choice(available),
        'profile_type': random.choices(PROFILE_NAMES, weights=[BEHAVIOR_PROFILES[p]['w'] for p in PROFILE_NAMES])[0],
        'from_db': False,
    }

def auto_recover(ban_step, config, db):
    """Adjust config based on failed step."""
    if ban_step in ("fill_email", "fill_name", "navigate"):
        # Likely IP/domain flagged — rotate preset and domain
        config['preset_idx'] = (config['preset_idx'] + random.randint(3, 6)) % 12
        sp(f"  [recovery] Switching to distant preset #{config['preset_idx']}")
    elif ban_step in ("fill_otp", "wait_otp"):
        # Speed detection — choose a slower profile
        config['profile_type'] = "slow"
        sp("  [recovery] Reducing to slow speed profile")
    elif ban_step in ("fill_password", "create"):
        # Form flagging — switch OS entirely
        new_os = random.choice([o for o in ['windows', 'macos', 'linux'] if o != config['os']])
        config['os'] = new_os
        sp(f"  [recovery] Switching OS to {new_os}")
    elif ban_step == "explore":
        # Post-signup issues — slower profile
        config['profile_type'] = "slow"
        sp("  [recovery] Post-signup: reducing speed")
    else:
        config['profile_type'] = "slow"
        sp("  [recovery] General: slowing down")
    return config

# ══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT CAPTURE
# ══════════════════════════════════════════════════════════════════════════════

def take_screenshot(page, label=""):
    """Save a screenshot of the current page state."""
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{ts}_{label[:30]}.png"
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', fname)
        path = str(SCREENSHOT_DIR / safe_name)
        page.screenshot(path=path, full_page=True)
        sp(f"    [screenshot] Saved to {safe_name}")
        return path
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════

def sp(*args, **kwargs):
    try:
        print(*args, **kwargs, flush=True)
    except (OSError, UnicodeEncodeError):
        try:
            safe = ' '.join(str(a) for a in args)
            safe = safe.encode('ascii', errors='replace').decode('ascii')
            print(safe, **kwargs, flush=True)
        except Exception:
            pass

def gen_name():
    if FAKER_OK:
        f = Faker('en_US')
        return f.name()
    first = ("James","Maria","John","Emma","Robert","Olivia","Michael","Sophia",
             "David","Isabella","William","Mia","Richard","Charlotte","Joseph","Amelia",
             "Thomas","Evelyn","Charles","Abigail","Daniel","Emily","Matthew","Harper",
             "Anthony","Ella","Mark","Scarlett","Steven","Grace","Andrew","Chloe",
             "Benjamin","Aurora","Samuel","Savannah","Luke","Aaliyah","Isaac","Kennedy",
             "Owen","Kinsley","Gabriel","Allison","Julian","Maya","Mateo","Ariana",
             "Cooper","Liliana","Xavier","Serenity","Dominic","Autumn","Miles","Leah",
             "Elias","Ayla","Hudson","Ivy","Asher","Valentina")
    last = ("Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
            "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
            "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
            "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
            "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill",
            "Mitchell","Carter","Roberts","Gomez","Phillips","Evans","Turner","Diaz",
            "Parker","Cruz","Edwards","Collins","Reyes","Stewart","Morris","Morales",
            "Murphy","Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper","Peterson",
            "Bailey","Reed","Kelly","Howard","Ramos","Kim","Cox","Ward",
            "Richardson","Watson","Brooks","Chavez","Wood","James","Bennett","Gray",
            "Mendoza","Ruiz","Hughes","Price","Alvarez","Castillo","Sanders","Patel",
            "Myers","Long","Ross","Foster","Jimenez","Powell","Jenkins","Perry")
    return f"{random.choice(first)} {random.choice(last)}"

def gen_email(name, domain):
    """Generate simple email — no dots, plus, hyphens, or underscores.
    Formats: firstlast@domain, firstNN@domain, firstlastNN@domain, lastNN@domain
    """
    parts = name.lower().split()
    first, last = parts[0], parts[-1] if len(parts) > 1 else 'user'
    domain = domain.lstrip('@')

    # Simple patterns only — no special characters in local part
    patterns = [
        lambda: f"{first}{last}{''.join(random.choices(string.digits, k=random.randint(0,2)))}@{domain}",
        lambda: f"{first}{random.randint(1, 999)}@{domain}",
        lambda: f"{first}{last}{random.randint(1, 99)}@{domain}",
        lambda: f"{last}{random.randint(1, 999)}@{domain}",
        lambda: f"{first}{random.randint(10, 99)}{last}@{domain}",
    ]
    return random.choice(patterns)()

def gen_password(length=None):
    """Generate password with variable length (14-20 chars) and varied patterns."""
    if length is None:
        length = random.randint(14, 20)
    u = string.ascii_uppercase; l = string.ascii_lowercase
    d = string.digits
    s_sets = ["!@#$%^&*()_+-=", "!@#$%^&*()", "_-+=!@#$%", "#$%&*+-=!?"]
    s = random.choice(s_sets)
    pw = [random.choice(u), random.choice(l), random.choice(d), random.choice(s)]
    pw += [random.choice(u + l + d + s) for _ in range(length - 4)]
    if random.random() < 0.30:
        pw.append(random.choice(s))
    random.shuffle(pw)
    return "".join(pw)

def verify_proxy_ip(page, proxy_cfg):
    """Quick single-attempt IP check via page.evaluate. Returns (True, info_dict) if residential,
    (False, info_dict) if datacenter, or (None, None) if check failed."""
    try:
        page.goto("https://ipinfo.io/json", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.0)
        body = page.evaluate("() => document.body?.textContent || ''") or ""
        if not body or len(body) < 10:
            return None, None
        info = json.loads(body)
        org = (info.get("org") or "").lower()
        ip = info.get("ip", "?")
        sp(f"    [i] Proxy IP: {ip} | Org: {org[:60]}")
        for bad in DATACENTER_ORGS:
            if bad in org:
                sp(f"    [!] DATACENTER IP DETECTED ({bad})")
                return False, info
        return True, info
    except Exception as e:
        sp(f"    [!] IP check failed: {e}")
        return None, None

def get_proxy_fallback(country='us'):
    """Get proxy from ProxyScrape free proxy API.
    Fetches fresh proxies, caches for 5 minutes, rotates per-country."""
    import requests as _req

    now = time.time()
    if not hasattr(get_proxy_fallback, '_pool'):
        get_proxy_fallback._pool = []
        get_proxy_fallback._pool_time = 0
        get_proxy_fallback._used = set()

    pool = get_proxy_fallback._pool
    pool_time = get_proxy_fallback._pool_time

    if not pool or (now - pool_time > 300):
        sp(f"  [i] Fetching fresh proxies for country={country}...")
        # Try HTTP first (more reliable), then SOCKS5
        for ptype in ['http', 'socks5']:
            try:
                url = f"https://api.proxyscrape.com/v2/?request=getproxies&proxytype={ptype}&timeout=5000&country={country}"
                r = _req.get(url, timeout=15)
                lines = [l.strip() for l in r.text.strip().splitlines() if l.strip()]
                if lines:
                    scheme = 'socks5' if ptype == 'socks5' else 'http'
                    pool = [f"{scheme}://{p}" for p in lines]
                    get_proxy_fallback._pool = pool
                    get_proxy_fallback._pool_time = now
                    get_proxy_fallback._used = set()
                    sp(f"  [+] Got {len(pool)} {ptype.upper()} proxies from ProxyScrape")
                    break
            except Exception as e:
                sp(f"  [!] ProxyScrape {ptype} failed: {e}")
        if not pool:
            sp(f"  [!] No proxies available from ProxyScrape for {country}")
            return None

    # Pick a proxy not yet used in this batch
    available = [p for p in pool if p not in get_proxy_fallback._used]
    if not available:
        get_proxy_fallback._used.clear()
        available = pool

    proxy_url = random.choice(available)
    get_proxy_fallback._used.add(proxy_url)

    return {
        'server': proxy_url,
        'username': '',
        'password': '',
    }

def parse_interval(raw):
    raw = raw.strip().lower()
    t = 0.0
    for m in re.findall(r'(\d+(?:\.\d+)?)\s*m', raw): t += float(m) * 60
    for s in re.findall(r'(\d+(?:\.\d+)?)\s*s', raw): t += float(s)
    if t == 0:
        try: t = float(raw)
        except ValueError: t = 120.0
    return t

def fmt_time(sec):
    m, s = int(sec) // 60, int(sec) % 60
    return f"{m}m {s}s" if m else f"{s}s"

# ══════════════════════════════════════════════════════════════════════════════
# ERROR CLASSIFICATION & TARGETED RECOVERY
# ══════════════════════════════════════════════════════════════════════════════

ERROR_PATTERNS = {
    'portal_signin_error': {'kw': ['portalsigninerror', 'sono.desc', 'try again'], 'desc': 'AWS portalSignInError → force page reload + rotate proxy'},
    'cloudflare': {'kw': ['cloudflare', 'checking your browser', 'just a moment', 'ddos protection'], 'desc': 'Cloudflare challenge → rotate OS+proxy country'},
    'aws_waf':   {'kw': ["enable javascript", "it's not you", 'something went wrong', 'try again later'], 'desc': 'AWS WAF/JS block → viewport+slow profile'},
    'datacenter':{'kw': ['datacenter'], 'desc': 'Datacenter IP → switch proxy country'},
    'proxy_ko':  {'kw': ['timeout', 'err_connection_timeout', 'err_proxy_connection'], 'desc': 'Proxy timeout → switch country'},
    'rate':      {'kw': ['rate limit', 'too many requests', '429'], 'desc': 'Rate limited → slow profile'},
    '403':       {'kw': ['403', 'forbidden', 'access denied'], 'desc': '403 block → full rotation'},
    'spa_blank': {'kw': ['blank', 'spa not rendered', 'content_ready'], 'desc': 'SPA not rendered → page reload + force retry'},
}

def capture_diagnostics(page):
    """Screenshot + body text + console messages."""
    d = {'url':'', 'error_keywords':[], 'body_snippet':'', 'screenshot':None}
    try: d['url'] = page.url
    except: pass
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        fn = f"error_{ts}.png"; sf = re.sub(r'[^a-zA-Z0-9_.-]','_',fn)
        page.screenshot(path=str(SCREENSHOT_DIR/sf), full_page=True)
        d['screenshot'] = sf
    except: pass
    try:
        body = page.evaluate("() => document.body?.innerText?.substring(0,2000)||''")
        for et, info in ERROR_PATTERNS.items():
            for k in info['kw']:
                if k in body.lower(): d['error_keywords'].append(k)
        d['body_snippet'] = body[:500]
    except: pass
    return d

def classify_error(diag, ban_step=None):
    kw = ' '.join(diag.get('error_keywords',[]))+' '+(diag.get('body_snippet','') or '')
    kwl = kw.lower()
    # Check portal_signin_error FIRST (most critical — AWS 500)
    for et, info in ERROR_PATTERNS.items():
        if any(k in kwl for k in info['kw']):
            if et == 'portal_signin_error':
                return et, 0.9, info['desc']
            return et, 0.7, info['desc']
    # Check for blank SPA page from ban_step
    if ban_step in ('fill_name', 'wait_otp'):
        body = (diag.get('body_snippet','') or '').lower()
        if not body or len(body.strip()) < 5:
            return 'spa_blank', 0.85, 'SPA never rendered (blank page)'
    if ban_step and '403' in str(ban_step):
        return '403', 0.6, '403 detected in step'
    if ban_step:
        return 'step_fail', 0.5, f'Failed at step: {ban_step}'
    return 'unknown', 0.3, 'No clear error pattern'

def targeted_recover(error_type, config, attempt_num):
    config = dict(config)
    if error_type == 'portal_signin_error':
        # AWS 500 — must reload page AND rotate everything
        config['os'] = random.choice(['macos','linux','windows'])
        config['viewport'] = random.choice(VIEWPORTS.get(config['os'], VIEWPORTS['windows']))
        config['profile_type'] = 'slow'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(3,6))%12
        sp(f"  [recovery] portalSignInError: full rotation OS→{config['os']}, preset→#{config['preset_idx']}, slow profile")
        sp(f"  [recovery] Will force page reload on next attempt")
    elif error_type == 'cloudflare':
        config['os'] = random.choice(['macos','linux'])
        config['profile_type'] = 'slow' if attempt_num>2 else 'variable'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(4,7))%12
        sp(f"  [recovery] Cloudflare: OS→{config['os']}, preset→#{config['preset_idx']}")
    elif error_type == 'aws_waf':
        config['viewport'] = random.choice(VIEWPORTS['macos']+VIEWPORTS['linux'])
        config['profile_type'] = 'slow'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(3,6))%12
        sp(f"  [recovery] AWS WAF: slow+preset→#{config['preset_idx']}")
    elif error_type == 'spa_blank':
        # SPA never rendered — reload page + rotate proxy
        config['os'] = random.choice(['macos','windows'])  # macOS worked better in tests
        config['viewport'] = random.choice(VIEWPORTS.get(config['os'], VIEWPORTS['windows']))
        config['profile_type'] = 'slow'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(2,5))%12
        sp(f"  [recovery] SPA blank: reload + OS→{config['os']}, preset→#{config['preset_idx']}, slow profile")
    elif error_type == 'datacenter':
        config['profile_type'] = 'slow'
        sp("  [recovery] Datacenter IP: slow profile")
    elif error_type == 'proxy_ko':
        config['profile_type'] = 'slow'
        sp("  [recovery] Proxy timeout: slow profile")
    elif error_type == 'rate':
        config['profile_type'] = 'slow'
        sp("  [recovery] Rate limit: slow profile")
    elif error_type == '403':
        config['os'] = random.choice(['macos','linux','windows'])
        config['profile_type'] = 'slow'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(2,5))%12
        sp(f"  [recovery] 403: OS→{config['os']}, preset→#{config['preset_idx']}")
    else:
        config['profile_type'] = 'slow'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(1,3))%12
        sp(f"  [recovery] Unknown: slow+preset→#{config['preset_idx']}")
    if attempt_num > 3:
        config['profile_type'] = 'slow'
        sp(f"  [recovery] Escalation #{attempt_num}: forced slow")
    if attempt_num > 5:
        config['os'] = random.choice([o for o in ['windows','macos','linux'] if o!=config.get('os','windows')])
        sp(f"  [recovery] Escalation #{attempt_num}: forced OS→{config['os']}")
    return config

# ══════════════════════════════════════════════════════════════════════════════
# OPERA VPN — prompt-based IP cycling
# ══════════════════════════════════════════════════════════════════════════════

def get_current_ip():
    for url in ['https://ipinfo.io/json','https://api.ipify.org?format=json','https://httpbin.org/ip']:
        try:
            import urllib.request
            return (json.loads(urllib.request.urlopen(url,timeout=10).read().decode())).get('ip') or '?'
        except: pass
    return '?'

def opera_vpn_cycle(wait_sec=90):
    """Wait for user to toggle Opera VPN, poll IP until change detected within wait_sec."""
    old = get_current_ip()
    sp("\n  ┌─ OPERA VPN CYCLING ───────────────────────────────────────")
    sp(f"  │ Current IP: {old}")
    sp(f"  │ ▶ Toggle Opera VPN OFF → ON now for a fresh residential IP")
    sp(f"  │ ▶ Watching up to {wait_sec}s for IP change...")
    sp("  └──────────────────────────────────────────────────────────")
    start = time.time()
    while time.time() - start < wait_sec:
        time.sleep(5)
        new = get_current_ip()
        remaining = wait_sec - int(time.time() - start)
        if new and new != old and new != '?':
            sp(f"\n  [+] IP changed from {old} → {new}")
            return new
        if remaining > 0:
            try:
                sys.stdout.write(f"\r  [*] IP: {new} — change? no — {fmt_time(remaining)} left   ")
                sys.stdout.flush()
            except: pass
    new = get_current_ip()
    sp(f"\n  [*] Timeout after {wait_sec}s — IP: {new}")
    return new or '?'

# ══════════════════════════════════════════════════════════════════════════════
# PANEL ACCOUNT VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def verify_panel_account(page, panel_url, email):
    """Check the Kiro provider page — is the account visible? Any 403/errors?"""
    sp("\n  ┌─ VERIFY PANEL ────────────────────────────────────────────")
    try:
        page.goto(f"{panel_url}/dashboard/providers/kiro", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5.0)
        body = (page.evaluate("() => document.body?.innerText?.substring(0,3000)||''") or '').lower()
        issues = []
        if '403' in body or 'forbidden' in body: issues.append('403_FORBIDDEN')
        if 'error' in body: issues.append('ERROR_STATE')
        if 'not available' in body: issues.append('UNAVAILABLE')
        if issues:
            sp(f"  │ ❌ Panel issues: {', '.join(issues)}")
            sp("  └──────────────────────────────────────────────────────")
            return False
        if email and email.lower() in body:
            sp(f"  │ ✅ {email} verified in panel")
        else:
            sp("  │ ⚠️ Account added but not yet visible")
        sp("  └──────────────────────────────────────────────────────")
        return True
    except Exception as e:
        sp(f"  │ [!] Verify: {e}")
        sp("  └──────────────────────────────────────────────────────")
        return False

# ══════════════════════════════════════════════════════════════════════════════
# CAMOUFOX NATIVE HUMAN INTERACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _bezier_t(t):
    return t * t * (3.0 - 2.0 * t)

def human_mouse_trail(page, x1, y1, x2, y2, steps=12):
    """Move mouse with a human-like bezier path. Uses Camoufox-native page.mouse.move()."""
    cp_x = (x1 + x2) / 2 + random.uniform(-30, 30)
    cp_y = (y1 + y2) / 2 + random.uniform(-50, 50)

    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt * mt * x1 + 2 * mt * t * cp_x + t * t * x2
        y = mt * mt * y1 + 2 * mt * t * cp_y + t * t * y2
        x += random.uniform(-2, 2)
        y += random.uniform(-2, 2)
        try:
            page.mouse.move(x, y)
        except Exception:
            pass
        delay = random.randint(12, 35)
        if i == steps - 1:
            delay = random.randint(30, 60)
        time.sleep(delay/1000)

def human_click(page, loc, timeout=3000):
    """Click an element using CloakBrowser humanized locator API.
    
    When CloakBrowser humanize is active, use locator.click() which goes through
    the full humanize pipeline (Bezier mouse curves, realistic timing).
    Falls back to raw mouse only if locator.click fails.
    """
    # Primary: use locator.click() — goes through CloakBrowser's humanize pipeline
    try:
        # Ensure element is visible first
        if loc.is_visible(timeout=timeout):
            loc.click(timeout=timeout)
            return True
    except Exception:
        pass
    
    # Fallback: raw mouse click (for edge cases where locator fails)
    try:
        box = loc.bounding_box(timeout=timeout)
        if not box:
            return False
        target_x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
        target_y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        page.mouse.click(target_x, target_y, delay=random.randint(10, 40))
        return True
    except Exception:
        return False

def human_type(page, text, delay_range=(30, 100)):
    """Type text using CloakBrowser humanized keyboard API.
    
    When CloakBrowser humanize is active, page.keyboard.type() goes through
    the humanize pipeline (per-character timing, thinking pauses, occasional typos).
    Falls back to raw keyboard for edge cases.
    """
    # Use CloakBrowser's humanized page.keyboard.type() which applies
    # per-character timing, thinking pauses, and self-correction
    try:
        # CloakBrowser humanize handles per-character timing automatically
        # Just ensure focus stays on the field - no random clicks
        page.keyboard.type(text)
    except Exception:
        # Fallback: raw character-by-character typing
        for i in range(len(text)):
            delay = random.randint(delay_range[0], delay_range[1])
            page.keyboard.type(text[i], delay=delay)
    time.sleep(random.randint(200,500)/1000)

def human_scroll(page, direction=1, amount=None):
    """Scroll page naturally using CloakBrowser humanized scroll.
    
    Uses page.mouse.wheel() which goes through CloakBrowser's humanize
    pipeline (accelerate -> cruise -> decelerate micro-steps).
    Falls back to raw mouse.wheel if needed.
    """
    if amount is None:
        amount = random.randint(100, 300)
    try:
        page.mouse.wheel(0, int(amount * direction))
        time.sleep(random.randint(200,500)/1000)
    except Exception:
        pass

def human_idle(page, min_sec=1, max_sec=3):
    """Brief idle pause."""
    try:
        time.sleep(random.uniform(min_sec, max_sec))
    except Exception:
        pass

def human_wait_page_load(page):
    """Wait briefly for page to load with human-like behavior."""
    time.sleep(random.uniform(0.8,2.0))
    try:
        page.mouse.wheel(0, random.randint(50, 150))
        time.sleep(random.randint(300,800)/1000)
    except Exception:
        pass

def click_text(page, text, timeout=5000):
    """Find and click a button/text element using CloakBrowser's locator API.
    
    Uses page.locator().click() which goes through CloakBrowser's humanize
    pipeline (Bezier mouse curves, realistic timing). Falls back to JS click
    only if locator fails.
    """
    # Primary: use CloakBrowser humanized locator
    try:
        btn = page.locator(f'text="{text}"').first
        if btn.is_visible(timeout=3000):
            btn.click(timeout=timeout)
            return True
    except Exception:
        pass
    
    # Try with text filter on buttons
    try:
        btn = page.locator('button').filter(has_text=re.compile(re.escape(text), re.I)).first
        if btn.is_visible(timeout=2000):
            btn.click(timeout=timeout)
            return True
    except Exception:
        pass
    
    # Fallback: JS click (last resort — bypasses humanize)
    try:
        result = page.evaluate(f"""(text) => {{
            const all = Array.from(document.querySelectorAll('button, a, [role="button"], span, div[role="button"]'));
            const target = all.find(el => {{
                const t = (el.textContent || '').trim().toLowerCase();
                return t.includes(text.toLowerCase()) && el.offsetWidth > 0 && el.offsetHeight > 0;
            }});
            if (!target) return false;
            target.scrollIntoView({{block: 'center', behavior: 'instant'}});
            target.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true, view: window}}));
            target.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true, view: window}}));
            target.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
            return true;
        }}""", text)
        return bool(result)
    except Exception:
        return False

def visible_locator(page, *selectors, timeout=5000):
    """Return first visible selector from a list. Returns None if none visible."""
    _ = timeout
    try:
        sel = page.evaluate("""(selectors) => {
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) return sel;
                }
            }
            return null;
        }""", list(selectors))
        if sel:
            return page.locator(sel).first
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
# Organic Navigation — 12 presets
# ══════════════════════════════════════════════════════════════════════════════

NAV_PRESETS = [
    {'via_google': True, 'search_query': 'kiro ai ide', 'click_signin': True, 'wait_mode': 'dom'},
    {'via_google': False, 'click_signin': True, 'wait_mode': 'load'},
    {'via_google': True, 'search_query': 'kiro login', 'click_signin': True, 'wait_mode': 'dom'},
    {'via_google': True, 'search_query': 'kiro ai', 'click_signin': True, 'wait_mode': 'network'},
    {'via_google': True, 'search_query': 'kiro app', 'click_signin': True, 'wait_mode': 'dom'},
    {'via_bing': True, 'search_query': 'kiro ide', 'click_signin': True, 'wait_mode': 'dom'},
    {'via_ddg': True, 'search_query': 'kiro ai ide', 'click_signin': True, 'wait_mode': 'dom'},
    {'via_google': False, 'click_signin': True, 'wait_mode': 'load', 'fast_type': True},
    {'via_google': True, 'search_query': 'kiro blog', 'click_signin': True, 'wait_mode': 'network',
     'explore_first': True, 'explore_urls': ['https://kiro.dev/blog', 'https://docs.kiro.dev']},
    {'via_google': True, 'search_query': 'kiro vs cursor review', 'click_signin': True, 'wait_mode': 'dom'},
    {'via_google': False, 'click_signin': True, 'wait_mode': 'load'},
    {'via_bing': True, 'search_query': 'kiro ai', 'click_signin': True, 'wait_mode': 'dom'},
]
SEARCH_ENGINES = ['google', 'bing', 'duckduckgo']

# ══════════════════════════════════════════════════════════════════════════════
# OIDC Client Registration & PKCE Signin
# ══════════════════════════════════════════════════════════════════════════════

REG_OIDC = "https://oidc.us-east-1.amazonaws.com"
REG_SCOPES = [
    "codewhisperer:completions", "codewhisperer:analysis",
    "codewhisperer:conversations", "codewhisperer:transformations",
    "codewhisperer:taskassist",
]
REG_REDIRECT_URI = "http://127.0.0.1:3128"
ISSUER_URL = "https://view.awsapps.com/start/"

def _b64url(d):
    return base64.urlsafe_b64encode(d).decode().rstrip("=")

# OIDC client registration (run once per session)
_oidc_client = {"client_id": None, "client_secret": None, "code_verifier": None,
                "code_challenge": None, "state_val": None, "signin_url": None}
_callback_server = {"instance": None, "signin_params": {}, "auth_code": ""}
# Captured tokens from account creation (for panel import)
_captured_tokens = {"refresh_token": "", "access_token": "", "email": ""}

def _start_callback_server():
    """Start the local callback server to capture Kiro signin redirects."""
    if _callback_server["instance"] is not None:
        return True

    # Free port 3128 if busy
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
                sp("    [CB] Authorization code captured")
                self_h.send_response(200)
                self_h.send_header("Content-Type", "text/html")
                self_h.end_headers()
                self_h.wfile.write(b"<html><body><h2>Registration complete!</h2></body></html>")
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
    import requests as _req

    if _oidc_client["client_id"] is not None:
        return True

    _oidc_client["code_verifier"] = secrets.token_urlsafe(64)
    _oidc_client["code_challenge"] = _b64url(
        hashlib.sha256(_oidc_client["code_verifier"].encode()).digest()
    )
    _oidc_client["state_val"] = secrets.token_urlsafe(32)

    try:
        resp = _req.post(f"{REG_OIDC}/client/register", json={
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
        _oidc_client["client_secret"] = reg["clientSecret"]
        sp(f"  [+] OIDC client registered: {_oidc_client['client_id'][:20]}...")

        _oidc_client["signin_url"] = f"https://app.kiro.dev/signin?" + urlencode({
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



def _signin_for_token_capture(page, email, password):
    """Sign in to Kiro via Builder ID to trigger consent page and capture auth_code.
    First signs out to ensure a fresh sign-in flow (which shows the consent page)."""
    # Reset callback state
    _callback_server["auth_code"] = ""
    
    try:
        # Step 1: Sign out of Kiro app to force fresh sign-in
        sp("  [*] Signing out of Kiro app...")
        try:
            page.goto("https://app.kiro.dev/settings", wait_until="domcontentloaded", timeout=30000)
            time.sleep(5.0)
            # Click sign out button
            page.evaluate("""() => {
                document.querySelectorAll('button, a, [role="button"]').forEach(el => {
                    const t = (el.innerText || '').toLowerCase();
                    if ((t.includes('sign out') || t.includes('sign-out') || t.includes('logout')) && el.offsetWidth > 0) {
                        el.click();
                    }
                });
            }""")
            time.sleep(3.0)
            sp("  [+] Sign out attempted")
        except Exception as e:
            sp(f"  [!] Sign out error (non-fatal): {e}")
        
        # Step 2: Navigate to Kiro sign-in page
        page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5.0)
        
        # Step 3: Click "Builder ID" button
        page.evaluate("""() => {
            document.querySelectorAll('button, a, div[role="button"]').forEach(el => {
                const t = (el.innerText || '').toLowerCase();
                if ((t.includes('builder id') || t.includes('builder')) && el.offsetWidth > 0) {
                    el.click();
                }
            });
        }""")
        sp("  [+] Builder ID clicked")
        time.sleep(5.0)
        
        # Step 4: Wait for AWS page and fill email
        for _ in range(15):
            time.sleep(2.0)
            url = page.url
            if 'signin.aws' in url or 'profile.aws' in url:
                sp(f"  [+] On AWS page: {url[:60]}")
                break
        
        # Fill email
        page.evaluate(f"""() => {{
            const inputs = document.querySelectorAll('input[type="email"], input[autocomplete="email"], input[placeholder*="email" i]');
            for (const el of inputs) {{
                if (el.offsetWidth > 0) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, '{email}');
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            }}
        }}""")
        sp(f"  [+] Email filled: {email}")
        time.sleep(1.0)
        
        # Click Continue
        page.evaluate("""() => {
            document.querySelectorAll('button').forEach(b => {
                const t = (b.innerText || '').toLowerCase();
                if (t.includes('continue') || t.includes('next')) { b.click(); }
            });
        }""")
        sp("  [+] Continue clicked")
        time.sleep(5.0)
        
        # Wait for password page
        for _ in range(15):
            time.sleep(2.0)
            pw_visible = page.evaluate("""() => {
                const inputs = document.querySelectorAll('input[type="password"]');
                for (const el of inputs) { if (el.offsetWidth > 0) return true; }
                return false;
            }""")
            if pw_visible:
                sp("  [+] Password page loaded")
                break
        
        # Fill password
        page.evaluate(f"""() => {{
            const inputs = document.querySelectorAll('input[type="password"]');
            for (const el of inputs) {{
                if (el.offsetWidth > 0) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, '{password}');
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            }}
        }}""")
        sp("  [+] Password filled")
        time.sleep(1.0)
        
        # Click Sign in
        page.evaluate("""() => {
            document.querySelectorAll('button').forEach(b => {
                const t = (b.innerText || '').toLowerCase();
                if (t.includes('sign in') || t.includes('submit') || t.includes('continue')) { b.click(); }
            });
        }""")
        sp("  [+] Sign in clicked")
        time.sleep(8.0)
        
        # Step 5: Wait for consent page ("Allow Kiro IDE to access your data?")
        sp("  [*] Waiting for consent page...")
        for _ in range(25):
            time.sleep(2.0)
            body = page.evaluate("() => (document.body?.innerText || '').toLowerCase()") or ""
            url = page.url
            if 'allow kiro' in body or 'access your data' in body or 'allow access' in body:
                sp("  [+] Consent page detected")
                break
            # Also check if redirected to callback (auth_code captured)
            if _callback_server.get("auth_code"):
                sp("  [+] Auth code already captured!")
                return True
        else:
            sp(f"  [!] Consent page not found. URL: {url[:80]}")
            return False
        
        # Step 6: Click Allow
        page.evaluate("""() => {
            document.querySelectorAll('button, a').forEach(el => {
                const t = (el.innerText || '').toLowerCase();
                if ((t.includes('allow') || t.includes('authorize')) && el.offsetWidth > 0) {
                    el.click();
                }
            });
        }""")
        sp("  [+] Allow clicked - waiting for callback...")
        
        # Step 7: Wait for callback to capture auth_code
        for _ in range(20):
            time.sleep(2.0)
            if _callback_server.get("auth_code"):
                sp("  [+] Auth code captured!")
                return True
        
        sp("  [!] No auth_code captured after Allow")
        return False
    except Exception as e:
        sp(f"  [!] Sign-in error: {e}")
        return False


def _exchange_auth_code_for_tokens():
    """Exchange the captured auth_code for access_token + refresh_token."""
    code = _callback_server.get("auth_code", "")
    if not code:
        # Try to get code from signin_params
        params = _callback_server.get("signin_params", {})
        code = params.get("code", "")
    if not code:
        sp("  [!] No auth_code available for token exchange")
        return False
    
    client_id = _oidc_client.get("client_id", "")
    client_secret = _oidc_client.get("client_secret", "")
    code_verifier = _oidc_client.get("code_verifier", "")
    
    if not all([client_id, client_secret, code_verifier]):
        sp("  [!] Missing OIDC client credentials for token exchange")
        return False
    
    try:
        import requests as _req
        sp("  [*] Exchanging auth code for tokens...")
        resp = _req.post(f"{REG_OIDC}/token", json={
            "clientId": client_id,
            "clientSecret": client_secret,
            "grantType": "authorization_code",
            "code": code,
            "redirectUri": REG_REDIRECT_URI,
            "codeVerifier": code_verifier,
        }, timeout=30, verify=False)
        tok = resp.json()
        if "accessToken" in tok:
            _captured_tokens["access_token"] = tok["accessToken"]
            _captured_tokens["refresh_token"] = tok.get("refreshToken", "")
            sp(f"  [+] Token exchange successful! Refresh: {_captured_tokens['refresh_token'][:30]}...")
            return True
        else:
            sp(f"  [!] Token exchange failed: {str(tok)[:200]}")
            return False
    except Exception as e:
        sp(f"  [!] Token exchange error: {e}")
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
    try:
        page.goto(authorize_url, wait_until="commit", timeout=120000)
    except Exception as e:
        sp(f"  [!] OIDC authorize commit failed: {e}, trying domcontentloaded...")
        try:
            page.goto(authorize_url, wait_until="domcontentloaded", timeout=120000)
        except Exception as e2:
            sp(f"  [!] OIDC authorize domcontentloaded also failed: {e2}")
            sp("  [!] Falling back to direct AWS signin...")
            try:
                page.goto("https://signin.aws.amazon.com/signin", wait_until="commit", timeout=60000)
                time.sleep(3)
                return True
            except Exception as e3:
                sp(f"  [!] Direct signin fallback also failed: {e3}")
                return False
    time.sleep(random.randint(2000,4000)/1000)
    return True

def organic_navigate_to_kiro(page, run_idx):
    """Navigate to Kiro signin with PKCE params (OIDC registration + callback server)."""
    sp(f"  [*] Navigation: preset #{run_idx % len(NAV_PRESETS)} — PKCE signin")

    # Ensure callback server and OIDC client are ready
    _start_callback_server()
    if not _register_oidc_client():
        sp("  [!] OIDC registration failed, falling back to direct signin")
        page.goto("https://app.kiro.dev/signin", wait_until="commit", timeout=90000)
        time.sleep(random.randint(1000,2000)/1000)
        return

    # Navigate to Kiro signin with PKCE params
    # Use commit for slow residential proxies, then wait for DOM manually
    try:
        page.goto(_oidc_client["signin_url"], wait_until="commit", timeout=120000)
    except Exception as e:
        sp(f"  [!] Page load slow (commit): {e}, trying domcontentloaded...")
        try:
            page.goto(_oidc_client["signin_url"], wait_until="domcontentloaded", timeout=90000)
        except Exception as e2:
            sp(f"  [!] Page load still slow: {e2}")
    time.sleep(random.uniform(2, 4))

# ══════════════════════════════════════════════════════════════════════════════
# State Detection — locator-first, evaluate() only as fallback
# ══════════════════════════════════════════════════════════════════════════════

def detect_state(page):
    """State detection using a single JS evaluate to avoid Playwright locator hangs."""
    url = page.url
    if not url: return "unknown"

    # Get hash fragment for SPA routes (profile.aws.amazon.com uses hash-based routing)
    hash_fragment = ""
    try:
        hash_fragment = page.evaluate("() => window.location.hash || ''").lower()
    except Exception:
        pass
    full_path = url.lower() + hash_fragment

    # URL-based fast paths (zero DOM access)
    if "/error" in url: return "error"
    if "verify" in full_path and "verify-otp" not in full_path: return "verify-otp"
    if "verify-otp" in full_path or "verifyotp" in full_path: return "verify-otp"
    if "password" in full_path and "set-password" not in full_path: return "password"
    if "set-password" in full_path or "create-password" in full_path: return "password"
    # AWS IAM Identity Center — treat as signin/signup page
    if "view.awsapps.com" in url:
        # Quick URL-based check: if it has an email input, it's signin; if it has a password field, it's password
        try:
            quick = page.evaluate("""() => {
                const body = (document.body?.innerText || '').toLowerCase();
                if (body.includes('allow kiro') || body.includes('allow access') || body.includes('access your data')) return 'oauth_consent';
                if (body.includes('enter your name') || body.includes('first name')) return 'signup-start';
                if (body.includes('create your password') || body.includes('ihr passwort')) return 'password';
                if (body.includes('verification code') || body.includes('enter the code')) return 'verify-otp';
                // Check for email input
                for (const el of document.querySelectorAll('input[type="email"]')) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) return 'signin';
                }
                // V8: Post-name-submit detection — name field has value but page hasn't advanced
                // This means Continue was clicked but AWS didn't move to OTP page
                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                for (const inp of inputs) {
                    if (inp.offsetWidth > 0 && inp.value && inp.value.trim().length > 2 && !(inp.value && inp.value.includes('@'))) {
                        // Name field has a value — this is post-submit stuck state
                        const ph = (inp.placeholder || '').toLowerCase();
                        const nm = (inp.name || '').toLowerCase();
                        const id = (inp.id || '').toLowerCase();
                        const ac = (inp.autocomplete || '').toLowerCase();
                        if (ph.includes('name') || nm.includes('name') || id.includes('name') || ac.includes('name') || ac.includes('given-name')) {
                            return 'post-name-submit';
                        }
                    }
                }
                return null;
            }""")
            if quick: return quick
        except Exception:
            pass
        return "signup-start"
    # Hash-based routes on profile.aws.amazon.com
    if "profile.aws" in url:
        if "verify-otp" in hash_fragment or "verifyotp" in hash_fragment:
            return "verify-otp"
        if "password" in hash_fragment or "set-password" in hash_fragment or "create-password" in hash_fragment:
            return "password"
        # Distinguish enter-email (after failed name submit) from signup-start (name page)
        if "enter-email" in hash_fragment:
            # Check body text for error or actual name page content
            try:
                body = page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''").lower()
                if "err-837" in body or "error processing" in body:
                    return "error"
                # If "enter your name" is present, this IS the name page (signup-start)
                if "enter your name" in body or "enter your name" in body.lower():
                    return "signup-start"
                # Check if there's a visible name input field
                has_name = page.evaluate("""() => {
                    for (const inp of document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])')) {
                        if (inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled) {
                            const ph = (inp.placeholder || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            const id = (inp.id || '').toLowerCase();
                            const ac = (inp.autocomplete || '').toLowerCase();
                            if (ph.includes('name') || nm.includes('name') || id.includes('name')) return true;
                            if (ac.includes('given-name') || ac.includes('family-name') || ac.includes('name')) return true;
                            if (inp.type === 'text' && !id.includes('awsccc') && !nm.includes('awsccc')) return true;
                        }
                    }
                    return false;
                }""") or False
                if has_name:
                    return "signup-start"
            except Exception:
                pass
            return "enter-email"
        if "signup/start" in hash_fragment or "#/signup/start" == hash_fragment:
            return "signup-start"
        # Check body text for error before defaulting to signup-start
        try:
            body_text = page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''").lower()
            if "err-837" in body_text or "error processing" in body_text:
                return "error"
            if "enter your name" in body_text:
                return "signup-start"
        except Exception:
            pass
        return "signup-start"
    # Only return signup-start if we AREN'T in the middle of a password/otp flow
    # or if the URL explicitly indicates a fresh signup start.
    # But check: if the page has visible password inputs, it's the password page (German: "Passwort")
    if "signup" in url and "aws" in url and "password" not in url.lower():
        try:
            has_pw = page.evaluate("""() => {
                for (const el of document.querySelectorAll('input[type="password"]')) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled) return true;
                }
                return false;
            }""") or False
            if has_pw:
                return "password"  # German password page ("Ihr Passwort erstellen")
        except Exception:
            pass
        return "signup-start"

    # Single JS call — checks DOM inputs + body text in one evaluate, no Playwright locators
    try:
        state = page.evaluate("""() => {
            const body = (document.body ? document.body.innerText.substring(0, 1000) : '').toLowerCase();
            const vis = (el) => el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;

            // Password field check
            for (const el of document.querySelectorAll('input[type="password"]')) {
                if (vis(el)) return 'password';
            }

            // OTP input check — modern selectors first
            const otpSels = [
                'input[autocomplete="one-time-code"]',
                'input[inputmode="numeric"]',
                'input[placeholder*="code" i]',
                'input[placeholder*="digit" i]',
                'input[placeholder*="otp" i]',
                'input[placeholder*="chiffre" i]',
                'input[aria-label*="code" i]',
                'input[aria-label*="verification" i]',
            ];
            for (const sel of otpSels) {
                for (const el of document.querySelectorAll(sel)) {
                    if (vis(el)) return 'verify-otp';
                }
            }
            // Single 6-char maxLength input = likely OTP
            for (const el of document.querySelectorAll('input:not([type="hidden"]):not([type="password"])')) {
                if (el.maxLength === 6 && vis(el)) return 'verify-otp';
            }

            // Body text fallback
            if (body.includes('verification code') || body.includes('enter the code') || body.includes('enter your verification'))
                return 'verify-otp';
            if (body.includes('create your password') || body.includes('create password') || body.includes('set a password'))
                return 'password';
            if (body.includes("it's not you") || body.includes('something went wrong') || body.includes("es liegt nicht an ihnen") || body.includes("ihre anfrage konnte derzeit nicht"))
                return 'error';

            return null;
        }""")
        if state: return state
    except Exception:
        pass

    # AWS IAM Identity Center (view.awsapps.com) — treat same as signin/signup
    if "view.awsapps.com" in url:
        try:
            body = page.evaluate("() => (document.body?.innerText || '').toLowerCase().substring(0, 1000)") or ''
            if any(w in body for w in ['enter your email', 'sign in', 'enter email']):
                return 'signin'
            if any(w in body for w in ['create your password', 'set a password', 'ihr passwort']):
                return 'password'
            if any(w in body for w in ['verification code', 'enter the code', 'otp']):
                return 'verify-otp'
            if any(w in body for w in ['enter your name', 'first name']):
                return 'signup-start'
            # V8: Post-name-submit detection
            has_name_value = page.evaluate("""() => {
                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                for (const inp of inputs) {
                    if (inp.offsetWidth > 0 && inp.value && inp.value.trim().length > 2 && !(inp.value && inp.value.includes('@'))) {
                        const ph = (inp.placeholder || '').toLowerCase();
                        const nm = (inp.name || '').toLowerCase();
                        const id = (inp.id || '').toLowerCase();
                        const ac = (inp.autocomplete || '').toLowerCase();
                        if (ph.includes('name') || nm.includes('name') || id.includes('name') || ac.includes('name') || ac.includes('given-name')) {
                            return true;
                        }
                    }
                }
                return false;
            }""") or False
            if has_name_value: return 'post-name-submit'
            # Default: check for email input
            has_email = page.evaluate("""() => {
                for (const el of document.querySelectorAll('input[type="email"]')) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) return true;
                }
                return false;
            }""") or False
            if has_email: return 'signin'
            return 'signup-start'
        except Exception:
            return 'signup-start'

    # Playwright locator fallback for edge cases
    if "profile.aws.amazon.com" in url:
        otp_loc = visible_locator(page, 'input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]',
                                  'input[placeholder*="code"]', 'input[placeholder*="digit"]',
                                  'input[placeholder*="otp"]', 'input[placeholder*="chiffre"]', timeout=2000)
        if otp_loc: return "verify-otp"
        pw_loc = visible_locator(page, 'input[type="password"]', timeout=2000)
        if pw_loc: return "password"
        return "signup-start"
    if "signin.aws" in url:
        pw_loc = visible_locator(page, 'input[type="password"]', timeout=2000)
        if pw_loc: return "signin"
        otp_loc = visible_locator(page, 'input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]',
                                  'input[placeholder*="code"]', 'input[placeholder*="digit"]',
                                  'input[placeholder*="otp"]', 'input[placeholder*="chiffre"]', timeout=2000)
        if otp_loc: return "verify-otp"
        name_loc = visible_locator(page, 'input[autocomplete*="name"]', 'input[placeholder*="name"]', timeout=2000)
        if name_loc: return "signup-start"
        return "signin"

    return "unknown"

def wait_for_state_change(page, from_state, timeout_sec=30):
    start = time.time()
    while time.time() - start < timeout_sec:
        time.sleep(2.0)
        ns = detect_state(page)
        if ns != from_state: return ns
    return None

# ══════════════════════════════════════════════════════════════════════════════
# OTP Polling
# ══════════════════════════════════════════════════════════════════════════════

def extract_code(text):
    if not text: return None
    m = re.search(r'[Vv]erification\s*[Cc]ode:?\s*(\d{6})', text)
    if m: return m.group(1)
    m = re.search(r'\b(\d{6})\b', text)
    if m: return m.group(1)
    return None

def poll_otp_imap(target_email, timeout=1800):
    """IMAP-based OTP polling. Searches by subject/keywords (not To: match)
    since catch-all forwarded emails may not match the To: header."""
    from automation.mail_reader import fetch_emails, mark_email_read, connect_imap
    sp(f"    [*] Polling OTP via IMAP for {target_email} ({timeout}s)...")
    start = time.time()
    seen = set()
    aws_kw = ["verify","builder","aws","amazon","aws builder id","verification code"]
    while time.time() - start < timeout:
        try:
            mails = []
            # Only INBOX — skip Spam/All Mail to avoid scanning 8000+ emails
            # IMAP SINCE filter: only emails from last 30 minutes
            from datetime import datetime as _dt, timedelta as _td
            since = (_dt.now() - _td(minutes=30)).strftime('%d-%b-%Y')
            try:
                mails.extend(fetch_emails(folder='INBOX', unread_only=True,
                                         limit=20, mark_as_read=False, since_date=since) or [])
            except Exception:
                pass
            for m in mails:
                uid = m["uid"]
                if uid in seen: continue
                seen.add(uid)
                to = (m.get("to","") or "").lower()
                subj = (m.get("subject","") or "").lower()
                body = (m.get("body_text","") or m.get("body_html","") or "").lower()
                # Match either: target_email in To, OR subject/body contains AWS keywords
                to_match = target_email.lower() in to
                kw_match = any(w in subj for w in aws_kw) or any(w in body for w in ["verification code","aws builder id"])
                if to_match or kw_match:
                    full_body = (m.get("body_text","") or m.get("body_html","") or "")
                    code = extract_code(full_body)
                    if code:
                        sp(f"    [+] OTP via IMAP: {code}")
                        try: mark_email_read(uid)
                        except: pass
                        return code
        except Exception as e:
            sp(f"    [!] OTP poll error: {e}")
        time.sleep(5)
    return None

def poll_otp_gmail_visual(page, timeout=120):
    """Visual Gmail OTP: open a new tab, navigate to Gmail, find the AWS verification email, read OTP code."""
    sp("    [*] Attempting visual Gmail OTP retrieval...")
    gmail_page = None
    try:
        gmail_page = page.context.new_page()
        gmail_page.set_default_timeout(30000)

        gmail_page.goto("https://mail.google.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(5.0,8.0))

        body_text = gmail_page.locator("body").text_content() or ""
        bl = body_text.lower()

        if "sign in" in bl or "log in" in bl:
            sp("    [!] Gmail not logged in, trying alternative URL...")
            gmail_page.goto("https://gmail.com", wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(5.0,8.0))
            body_text = gmail_page.locator("body").text_content() or ""
            bl = body_text.lower()

        if "sign in" in bl or "log in" in bl:
            sp("    [!] Gmail not logged in — cannot use visual OTP")
            return None

        sp("    [+] Gmail loaded, scanning for AWS verification email...")
        start = time.time()

        while time.time() - start < timeout:
            body_text = gmail_page.locator("body").text_content() or ""
            bl = body_text.lower()
            aws_found = any(kw in bl for kw in ["aws", "amazon web services", "builder id", "verification code", "kiro"])

            if aws_found:
                for sel in [
                    'div:has-text("AWS")', 'div:has-text("Amazon")',
                    'div:has-text("Builder ID")', 'div:has-text("verification")',
                    'span:has-text("AWS")', 'span:has-text("Amazon")',
                ]:
                    try:
                        loc = gmail_page.locator(sel).first
                        if loc.is_visible(timeout=2000):
                            human_click(gmail_page, loc)
                            time.sleep(random.uniform(3.0,6.0))
                            break
                    except Exception:
                        pass

                email_body = gmail_page.locator("body").text_content() or ""
                code = extract_code(email_body)
                if code:
                    sp(f"    [+] OTP via visual Gmail: {code}")
                    return code

                human_scroll(gmail_page)
                time.sleep(random.uniform(3.0,5.0))

            human_scroll(gmail_page, direction=-1)
            time.sleep(random.uniform(3.0,6.0))

        sp("    [!] Visual Gmail OTP timed out")
        return None

    except Exception as e:
        sp(f"    [!] Visual Gmail OTP error: {e}")
        return None
    finally:
        try:
            if gmail_page and not gmail_page.is_closed():
                gmail_page.close()
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# ACCOUNT CREATION — with step tracking and checkpoint support
# ══════════════════════════════════════════════════════════════════════════════

def create_account(page, domain, run_idx=0, step_results=None, mail_provider=None):
    """Create AWS Builder ID with ONLY Camoufox native interactions + step tracking.
    
    If mail_provider is provided, uses it to create a disposable mailbox
    and overrides the email address with the provider's generated email.
    """
    if step_results is None:
        step_results = {}

    name = gen_name()
    # V8: If mail_provider is provided, use disposable email instead of generated one
    if mail_provider:
        try:
            disposable_email = mail_provider.create_mailbox()
            if disposable_email:
                email = disposable_email
                sp(f"  [+] Disposable email created: {email}")
            else:
                email = gen_email(name, domain)
                sp(f"  [!] Mail provider returned empty, falling back to generated")
        except Exception as e:
            sp(f"  [!] Mail provider error: {e}, falling back to generated email")
            email = gen_email(name, domain)
    else:
        email = gen_email(name, domain)
    password = gen_password()
    sp(f"  Name:     {name}")
    sp(f"  Email:    {email}")
    sp(f"  Password: {password}")

    # V6: Cookie warming — browse normal sites briefly before hitting Kiro signup
    # Only do lightweight warming if proxy is fast enough
    sp("  [+] Cookie warming: browsing normal sites...")
    try:
        # Use commit timeout (not domcontentloaded) for slow proxies
        page.goto("https://www.google.com", wait_until="commit", timeout=8000)
        time.sleep(random.uniform(2, 3))
        sp("  [+] Cookie warming complete")
    except Exception as e:
        sp(f"  [!] Cookie warming skipped (slow proxy, non-fatal): {e}")

    step_results['navigate'] = True
    organic_navigate_to_kiro(page, run_idx)

    step_results['click_builder'] = True
    
    # Wait for Kiro page to fully render the Builder ID button (slow residential proxy)
    sp("  [*] Waiting for Kiro signin page to render...")
    try:
        page.wait_for_selector('button:has-text("Builder ID")', timeout=30000)
        sp("  [+] Kiro signin page rendered")
    except Exception:
        sp("  [!] Builder ID button not found after 30s, checking page state...")
        # Take screenshot for debugging
        try:
            page.screenshot(path="/home/ubuntu/debug_kiro_page.png")
            sp("  [+] Screenshot saved to /home/ubuntu/debug_kiro_page.png")
        except: pass
        # Check what's on the page
        title = page.title()
        url = page.url
        sp(f"  [!] Page title: {title} | URL: {url[:80]}")
        # Try waiting longer
        time.sleep(5)
    
    sp("  Clicking AWS Builder ID (JS dispatch)...")
    builder_clicked = False
    for _attempt in range(3):
        try:
            builder_clicked = page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const target = btns.find(b => b.textContent.includes('Builder ID') && b.offsetWidth > 0);
                if (!target) return false;
                target.scrollIntoView({block: 'center', behavior: 'instant'});
                target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return true;
            }""")
            if builder_clicked:
                break
        except Exception as e:
            sp(f"  [!] Click attempt {_attempt+1} failed: {e}")
        if not builder_clicked and _attempt < 2:
            time.sleep(3)
    
    if not builder_clicked:
        sp("  [!] Could not find AWS Builder ID button after 3 attempts, trying locator...")
        try:
            btn = page.locator('button:has-text("Builder ID")').first
            btn.click(timeout=10000)
            builder_clicked = True
        except Exception as e:
            sp(f"  [!] Locator also failed: {e}")
    
    if not builder_clicked:
        raise Exception("Could not find AWS Builder ID button")
    sp("  [+] AWS Builder ID clicked (JS)")

    # After clicking Builder ID, Kiro SPA sends a callback to our local server.
    # Wait for the callback, then navigate to OIDC authorize URL.
    sp("  [*] Waiting for Kiro callback...")
    for _ in range(30):
        time.sleep(3.0)
        if _callback_server["signin_params"]:
            sp(f"  [+] Signin callback received: {dict(_callback_server['signin_params'])}")
            break
    
    if _callback_server["signin_params"]:
        # Navigate to OIDC authorize URL
        oidc_ok = _navigate_to_oidc_authorize(page)
        if oidc_ok:
            sp("  [+] Navigated to OIDC authorize page")
        else:
            sp("  [!] OIDC authorize navigation failed, falling back to direct signin...")
    else:
        sp("  [!] No callback received, trying direct AWS signin...")
    
    # Fallback: navigate directly to AWS signin if OIDC failed or no callback
    if not oidc_ok or not _callback_server["signin_params"]:
        try:
            # First check if we're on chrome-error page and navigate away
            if page.url and 'chrome-error' in page.url:
                sp("  [*] On chrome-error page, navigating away...")
                page.evaluate("() => location.href = 'about:blank'")
                time.sleep(1)
            page.goto("https://signin.aws.amazon.com/signin", wait_until="commit", timeout=30000)
            time.sleep(3)
            sp("  [+] Navigated directly to AWS signin")
        except Exception as e:
            sp(f"  [!] Direct AWS signin failed: {e}")
            # Last resort: try navigating to about:blank first then AWS
            try:
                page.evaluate("() => { location.href = 'about:blank'; }")
                time.sleep(2)
                page.goto("https://signin.aws.amazon.com/signin", wait_until="commit", timeout=30000)
                time.sleep(3)
                sp("  [+] Navigated directly to AWS signin (retry)")
            except Exception as e2:
                sp(f"  [!] Direct AWS signin retry also failed: {e2}")

    # Wait for AWS page (either from OIDC authorize redirect or direct)
    for _idx in range(30):
        time.sleep(3.0)
        try:
            has_aws = page.evaluate("""() => {
                for (const i of document.querySelectorAll('input[type="email"]')) { if (i.offsetWidth > 0) return 'email'; }
                const t = document.title;
                if (t && t.includes('Amazon Web Services')) return 'title';
                if (t && t.includes('AWS access portal')) return 'consent';
                if ((document.body?.innerText||'').includes('Continue with Google')) return 'content';
                if (location.href.includes('signin.aws') || location.href.includes('amazonaws.com')) return 'url';
                if (location.href.includes('view.awsapps.com')) return 'consent_url';
                if (location.href.includes('127.0.0.1') || location.href.includes('localhost')) return 'callback';
                if ((document.body?.innerText||'').includes('Registration complete')) return 'callback_done';
                if ((document.body?.innerText||'').includes('it\\u0027s not you') || (document.body?.innerText||'').includes("it's not you")) return 'error';
                const err = (document.body?.innerText||'').match(/"error":\\s*"([^"]+)"/);
                if (err) return 'error:' + err[1];
                return false;
            }""")
            if has_aws:
                sp(f"  [+] AWS page detected ({has_aws})")
                break
        except Exception:
            pass
        if _idx % 5 == 0:
            take_screenshot(page, f"aws_wait_{_idx}")
            try:
                _page_debug = page.evaluate("""() => ({
                    url: location.href,
                    title: document.title,
                    bodyLen: (document.body?.innerText||'').length,
                    bodySnippet: (document.body?.innerText||'').substring(0, 300),
                    scripts: document.querySelectorAll('script').length,
                    inputs: document.querySelectorAll('input').length,
                    inputDetails: Array.from(document.querySelectorAll('input')).map(i => ({type: i.type, name: i.name, id: i.id, vis: i.offsetWidth > 0, placeholder: i.placeholder||''})),
                    allButtons: Array.from(document.querySelectorAll('button, a')).map(b => ({tag: b.tagName, text: (b.textContent||'').trim().substring(0,50), href: (b.href||'').substring(0,80), vis: b.offsetWidth > 0})).filter(b => b.vis).slice(0,20),
                    htmlLen: (document.body?.innerHTML||'').length,
                })""")
                sp(f"  [dbg] url={_page_debug['url'][:120]}")
                sp(f"  [dbg] title={_page_debug['title']}")
                sp(f"  [dbg] htmlLen={_page_debug['htmlLen']} bodyLen={_page_debug['bodyLen']} scripts={_page_debug['scripts']} inputs={_page_debug['inputs']}")
                sp(f"  [dbg] inputs={_page_debug['inputDetails']}")
                sp(f"  [dbg] buttons={_page_debug['allButtons']}")
                sp(f"  [dbg] body='{_page_debug['bodySnippet'][:200]}'")
            except Exception as e:
                sp(f"  [dbg] page eval failed: {e}")
            sp(f"  Waiting for AWS page... ({page.url[:80]})")
    else:
        # If we have OIDC params but AWS page still not loaded, try direct authorize
        if _callback_server["signin_params"] and _oidc_client["client_id"]:
            sp("  [*] Retrying OIDC authorize navigation...")
            _navigate_to_oidc_authorize(page)
            for _ in range(15):
                time.sleep(3.0)
                try:
                    has_aws = page.evaluate("""() => {
                        for (const i of document.querySelectorAll('input[type="email"]')) { if (i.offsetWidth > 0) return 'email'; }
                        const t = document.title;
                        if (t && t.includes('Amazon Web Services')) return 'title';
                        if (t && t.includes('AWS access portal')) return 'consent';
                        if (location.href.includes('signin.aws') || location.href.includes('amazonaws.com')) return 'url';
                        if (location.href.includes('view.awsapps.com')) return 'consent_url';
                        if (location.href.includes('127.0.0.1') || location.href.includes('localhost')) return 'callback';
                        return false;
                    }""")
                    if has_aws:
                        sp(f"  [+] AWS page detected on retry ({has_aws})")
                        break
                except Exception:
                    pass
            else:
                raise Exception("AWS page did not load (OIDC authorize failed)")
        else:
            raise Exception("AWS page did not load")

    human_wait_page_load(page)
    human_scroll(page)

    # Check if we're on the consent page (Allow/Deny) vs email/password page
    is_consent = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        return btns.some(b => b.textContent.trim().toLowerCase().includes('allow access'));
    }""")

    if is_consent:
        sp("  [+] Consent page detected — clicking Allow access")
        take_screenshot(page, "consent_before")
        # Click Allow access
        allow_clicked = False
        try:
            btn = page.locator('button').filter(has_text=re.compile(r'allow\s+access', re.I)).first
            if btn.is_visible(timeout=5000):
                btn.click(timeout=10000)
                allow_clicked = True
                sp("  [+] Clicked Allow access (native)")
        except Exception:
            pass
        if not allow_clicked:
            allow_clicked = page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t.includes('allow access') && b.offsetWidth > 0 && !b.disabled) {
                        b.click(); return true;
                    }
                }
                return false;
            }""")
            if allow_clicked:
                sp("  [+] Clicked Allow access (JS)")
        
        if allow_clicked:
            time.sleep(10.0)
            take_screenshot(page, "consent_after_allow")
            # Check if we redirected back to Kiro
            new_url = page.url
            sp(f"  [+] After Allow: {new_url[:120]}")
            # The flow may be complete — the callback server should have received the code
            step_results['fill_email'] = True
            step_results['fill_password'] = True
            return (name, email, password)
        else:
            sp("  [!] Could not click Allow access")
    else:
        click_text(page, "Accept", timeout=5000)

    email_loc = None
    for _ in range(20):
        time.sleep(1.5)
        try:
            has_email = page.evaluate("""() => {
                for (const i of document.querySelectorAll('input')) {
                    if (i.offsetWidth <= 0 || i.offsetHeight <= 0 || i.disabled) continue;
                    if (i.type === 'email') return true;
                    if ((i.placeholder||'').includes('@')) return true;
                } return false;
            }""")
            if has_email:
                sp("  [+] Email input found")
                email_loc = page.locator('input[type="email"]').first
                break
        except Exception:
            pass
        sp(f"  Waiting for email input...")
    if not email_loc:
        sp("  [!] Using fallback for email input")
        try:
            email_loc = page.locator('input[type="email"]').first
            if not email_loc.is_visible(timeout=3000):
                email_loc = None
        except Exception:
            pass

    step_results['fill_email'] = True
    if email_loc or True:
        if not email_loc:
            try:
                email_loc = page.locator('input[type="email"]').first
            except Exception:
                pass
        if email_loc:
            human_click(page, email_loc)
            # V5: Variable typing rhythm delay
            time.sleep(random.randint(500,1200)/1000)
            human_type(page, email)
            # FWCIM needs time to register typing behavior
            time.sleep(random.randint(500,1200)/1000)
        sp("  [+] Email filled")
        # Shorter delay before submitting to prevent session expiry on slow proxies
        time.sleep(random.uniform(1.5,3.0))
        # Robust Submit - Try multiple methods (data-testid first, then text, then JS, then Enter)
        submitted = False
        for method in ["testid", "text", "js", "fallback"]:
            if method == "testid":
                try:
                    btn = page.locator('[data-testid="test-primary-button"]').first
                    if btn.is_visible(timeout=3000):
                        # V5: Hover before clicking
                        btn.hover()
                        time.sleep(random.randint(500,1200)/1000)
                        btn.click()
                        submitted = True
                        sp("  [+] Continue submitted via data-testid")
                except Exception:
                    pass
            elif method == "text":
                # V5: Use locator for humanized hover/click if possible
                try:
                    btn = page.locator('button').filter(has_text=re.compile(r'continue|next', re.I)).first
                    if btn.is_visible(timeout=2000):
                        btn.hover()
                        time.sleep(random.randint(500,1000)/1000)
                        btn.click()
                        submitted = True
                except:
                    submitted = click_text(page, "Continue", timeout=5000) or \
                                click_text(page, "Next", timeout=3000)
            elif method == "js" and not submitted:
                submitted = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const target = btns.find(b => (b.textContent.includes('Continue') || b.textContent.includes('Next')) && b.offsetWidth > 0);
                    if (target) {
                        target.click();
                        return true;
                    }
                    return false;
                }""")
            elif method == "fallback" and not submitted:
                try:
                    page.keyboard.press("Enter")
                    submitted = True
                except: pass
            
            if submitted:
                sp(f"  [+] Continue submitted via {method}")
                break
        
        if not submitted:
            sp("  [!] Failed to submit email")
        
        time.sleep(random.uniform(1.0,2.5))

    # Wait for redirect to profile.aws.amazon.com and SPA to fully render
    # FWCIM needs extra time between page transitions
    sp("  [*] Waiting for AWS profile page and SPA render...")
    continue_clicks = 0
    for _ in range(25):
        time.sleep(3.0)
        try:
            # Check if we're on the AWS profile page
            is_aws = page.evaluate("""() => {
                const u = location.href;
                if (u.includes('profile.aws.amazon.com')) return 'aws_profile';
                if (u.includes('signin.aws')) return 'signin_page';
                if (u.includes('signup') && u.includes('aws')) return 'signup_page';
                if (u.includes('view.awsapps.com')) return 'aws_idc';
                return null;
            }""")
            if is_aws:
                # Now check if the SPA has actually RENDERED (has visible content)
                body_check = page.evaluate("""() => {
                    const t = document.body?.innerText || '';
                    if (t.length > 50) return 'content_ready';
                    // Check for any visible non-hidden input
                    for (const i of document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"])')) {
                        if (i.offsetWidth > 0 && i.offsetHeight > 0) return 'input_ready';
                    }
                    return null;
                }""")
                if body_check in ('content_ready', 'input_ready'):
                    sp(f"  [+] AWS page detected, content ready: {body_check}")
                    break
                else:
                    # Check for portalSignInError (AWS 500)
                    diag_body = ''
                    try:
                        diag_body = page.evaluate("() => (document.body?.innerText||'').substring(0,200)" or '')
                    except: pass
                    if 'portalsigninerror' in diag_body.lower() or 'sono.desc' in diag_body.lower():
                        sp(f"  [!] portalSignInError detected — forcing page reload...")
                        step_results['restart_full'] = True
                        break
                    sp(f"  [*] AWS page loaded but SPA not rendered yet, waiting...")
                    # After 10 iterations (30s), try a hard reload
                    if _ == 10:
                        sp(f"  [*] SPA not rendered after 30s — hard reload...")
                        try:
                            page.goto(page.url, wait_until="commit", timeout=15000)
                            time.sleep(5.0)
                        except Exception as e:
                            sp(f"  [!] Reload failed: {e}")
                    # After 20 iterations (60s), give up and retry
                    if _ == 20:
                        sp(f"  [!] SPA not rendered after 60s — will retry with fresh config")
                        step_results['restart_full'] = True
                        break
            elif "signin.aws" in page.url:
                # Still on signin page - only click Continue max 3 times
                continue_clicks += 1
                if continue_clicks <= 3:
                    sp(f"  [*] Still on signin page, clicking Continue ({continue_clicks}/3)...")
                    click_text(page, "Continue", timeout=2000)
                else:
                    if continue_clicks == 4:
                        sp(f"  [*] Waiting longer for SPA to process (slow proxy)...")
        except Exception:
            pass

    human_scroll(page)

    for attempt in range(30):
        if step_results.get('force_password'):
            state = "password"
            step_results['force_password'] = False
            sp(f"  [{attempt}] state={state} (forced)")
        else:
            state = detect_state(page)
            sp(f"  [{attempt}] state={state}")

        if state == "oauth_consent":
            # OIDC OAuth consent page: "Allow Kiro IDE to access your data?"
            sp("  [*] OAuth consent page detected — clicking Allow...")
            consent_clicked = False
            for _consent_attempt in range(5):
                try:
                    # Try native Playwright click first
                    clicked = False
                    for sel in ['button:has-text("Allow access")', 'button:has-text("Allow")', 'button:has-text("Confirm and continue")']:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=2000):
                                btn.click()
                                sp(f"  [+] Allow clicked (native: {sel})")
                                clicked = True
                                consent_clicked = True
                                break
                        except: pass
                    if not clicked:
                        # JS fallback
                        clicked = page.evaluate("""() => {
                            const btns = Array.from(document.querySelectorAll('button'));
                            const target = btns.find(b => {
                                const t = b.textContent.toLowerCase();
                                return (t.includes('allow') || t.includes('confirm and continue')) && b.offsetWidth > 0;
                            });
                            if (target) { target.click(); return true; }
                            return false;
                        }""")
                        if clicked:
                            sp("  [+] Allow clicked (JS fallback)")
                            consent_clicked = True
                    if consent_clicked:
                        break
                except Exception as e:
                    sp(f"  [!] Consent click attempt {_consent_attempt+1} failed: {e}")
                time.sleep(2.0)
            if consent_clicked:
                # Wait for the callback redirect (OIDC PKCE flow)
                for _cb_wait in range(30):
                    time.sleep(3.0)
                    try:
                        cb_url = page.url
                        if "127.0.0.1" in cb_url or "localhost" in cb_url:
                            cb_body = (page.evaluate("() => (document.body?.innerText || '').toLowerCase().trim()") or '')
                            if 'registration complete' in cb_body or 'success' in cb_body:
                                sp(f"  [!] ACCOUNT CREATION CONFIRMED via OIDC callback")
                                take_screenshot(page, "registration_complete")
                                try:
                                    page.goto("https://app.kiro.dev", wait_until="domcontentloaded", timeout=30000)
                                    human_wait_page_load(page)
                                except Exception:
                                    pass
                                return name, email, password
                    except Exception:
                        pass
                    sp(f"  [*] Waiting for callback... ({_cb_wait+1})")
                else:
                    sp("  [!] Callback timeout, but account might be created. Proceeding to Kiro...")
                    try:
                        page.goto("https://app.kiro.dev", wait_until="domcontentloaded", timeout=30000)
                        human_wait_page_load(page)
                    except Exception:
                        pass
                    return name, email, password
            else:
                sp("  [!] Could not click Allow on consent page")
            attempt += 1
            continue

        if state == "signup-start":
            if step_results.get('fill_otp'):
                # ADD DIAGNOSTICS: print URL and body text
                try:
                    diag_url = page.url
                    diag_body = (page.evaluate("() => document.body?.innerText?.substring(0,500)||''") or "")
                    sp(f"  [!] LOOP DETECTED: URL: {diag_url}")
                    sp(f"  [!] LOOP DETECTED: Body: {diag_body[:300]}")
                except Exception as e:
                    sp(f"  [!] LOOP DETECTED: diag error: {e}")
                
                if "es liegt nicht an ihnen" in diag_body.lower() or "ihre anfrage konnte derzeit nicht" in diag_body.lower():
                    sp("  [!] AWS 500 error page detected (German) — restarting full flow...")
                    step_results['restart_full'] = True
                    break
                if "sitzung abgelaufen" in diag_body.lower() or "session expired" in diag_body.lower() or "session has expired" in diag_body.lower() or "starte deinen workflow" in diag_body.lower():
                    sp("  [!] Session expired — restarting email flow...")
                    step_results['restart_email'] = True
                    step_results['fill_name'] = False
                    step_results['fill_otp'] = False
                    step_results['fill_password'] = False
                    break
                
                if not diag_body or len(diag_body.strip()) == 0:
                    sp("  [*] SPA loading after OTP, waiting for content...")
                    for render_wait in range(30):
                        time.sleep(2.0)
                        try:
                            new_body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                            if len(new_body) > 20:
                                sp(f"  [+] SPA rendered ({len(new_body)} chars)")
                                break
                        except Exception:
                            pass
                        if render_wait % 5 == 4:
                            sp(f"  [*] Still waiting... ({render_wait*2}s)")
                    # Re-check state after waiting
                    ns = detect_state(page)
                    sp(f"  [post-wait] state={ns}")
                    if ns != "signup-start":
                        state = ns
                    else:
                        diag_body = (page.evaluate("() => document.body?.innerText?.substring(0,500)||''") or "")
                
                # Check if it's actually the password page (English + German)
                if 'password' in diag_url.lower() or 'passwort' in diag_url.lower() \
                    or 'create password' in diag_body.lower() or 'create your password' in diag_body.lower() \
                    or 'password' in diag_body.lower() or 'passwort' in diag_body.lower() \
                    or 'ihr passwort' in diag_body.lower() or 'passwort bestätigen' in diag_body.lower():
                    sp("  [!] LOOP DETECTED but page is PASSWORD page! Setting force_state...")
                    step_results['force_password'] = True
                    continue
                else:
                    sp("  [!] LOOP DETECTED: Transitioned back to signup-start after OTP submission.")
                    sp("      This usually means the OTP was rejected or the session expired.")
                    raise Exception("AWS signup loop detected after OTP submission")

            # V8: Handle post-name-submit stuck state — name was filled but page didn't advance
            if state == "post-name-submit":
                sp("  [!] POST-NAME-SUBMIT stuck — name field has value but page won't advance")
                sp("      AWS likely rejected the submit. Force restart...")
                try:
                    diag_body = (page.evaluate("() => (document.body?.innerText||'').substring(0,300)") or "")
                    sp(f"      Body: {diag_body[:200]}")
                except: pass
                # Mark for full restart — this is not a normal state, AWS rejected us
                step_results['restart_full'] = True
                break

            step_results['fill_name'] = True
            time.sleep(2.0)
            
            # Check for OAuth consent page: "Allow Kiro IDE to access your data?"
            # This appears on view.awsapps.com after OIDC flow
            try:
                oauth_body = (page.evaluate("() => (document.body?.innerText || '').toLowerCase().substring(0, 500)") or '')
                if 'allow kiro' in oauth_body or 'allow access' in oauth_body or 'access your data' in oauth_body:
                    sp("  [*] OAuth consent page detected — clicking Allow...")
                    # Try native Playwright click first
                    clicked = False
                    try:
                        allow_btn = page.locator('button:has-text("Allow access"), button:has-text("Allow"), button:has-text("allow")').first
                        if allow_btn.is_visible(timeout=3000):
                            allow_btn.click(timeout=5000)
                            sp("  [+] Allow clicked (native)")
                            clicked = True
                    except Exception:
                        pass
                    if not clicked:
                        # JS fallback
                        clicked = page.evaluate("""() => {
                            const btns = document.querySelectorAll('button');
                            for (const b of btns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if ((t.includes('allow access') || t.includes('allow') || t.includes('approve')) && b.offsetWidth > 0 && !b.disabled) {
                                    b.click();
                                    return true;
                                }
                            }
                            return false;
                        }""")
                        if clicked:
                            sp("  [+] Allow clicked (JS)")
                    time.sleep(5.0)
                    # After clicking Allow, the page might redirect to the signup page or to Kiro
                    continue
            except Exception:
                pass
            
            # Check for cookie consent / blank page / session timeout and handle it
            try:
                body_text = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                if "enable JavaScript" in body_text.lower():
                    sp("  [!] JS not loaded -- reloading...")
                    page.goto(page.url, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(3.0)
                    continue
                elif "session timed out" in body_text.lower() or "oh no" in body_text.lower():
                    sp("  [!] Session timed out! Restarting workflow from signin page...")
                    page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(3.0)
                    attempt = 0
                    continue
                elif "cookie" in body_text.lower() or "privacy" in body_text.lower() or len(body_text) < 50:
                    # Check if it's portalSignInError
                    if 'portalsigninerror' in body_text.lower() or 'sono.desc' in body_text.lower():
                        sp(f"  [!] portalSignInError detected on signup page — forcing restart...")
                        step_results['restart_full'] = True
                        break
                    # Cookie consent page or blank page - accept cookies and wait
                    sp(f"  [*] Cookie/blank page detected ({len(body_text)} chars), accepting...")
                    dismissed = False
                    # Try visible buttons first
                    for btn_text in ["Accept", "Accepter", "Save preferences", "Decline", "Customize", "Dismiss", "Refuser"]:
                        if click_text(page, btn_text, timeout=2000):
                            dismissed = True
                            sp(f"  [+] Consent dismissed via: {btn_text}")
                            break
                    if not dismissed:
                        # JS fallback: handle multi-step consent overlay (supports English, French, Spanish, German)
                        sp("  [*] Consent buttons not visible, trying JS dismissal...")
                        try:
                            for consent_step in range(5):  # Multi-step consent may have up to 5 steps
                                js_dismissed = page.evaluate("""() => {
                                    const allBtns = document.querySelectorAll('button, [role="button"]');
                                    const texts = [];
                                    allBtns.forEach(b => texts.push((b.textContent || '').trim()));
                                    const allText = texts.join('|').toLowerCase();
                                    
                                    // Check if this is a consent overlay (multi-language)
                                    const consentKeywords = [
                                        'accept', 'accepter', 'aceptar', 'acceptieren',
                                        'refuser', 'refuse', 'rechazar', 'ablehnen',
                                        'decline', 'personnaliser', 'personalizar', 'personalisieren',
                                        'customize', 'save preferences', 'enregistrer les pr\u00e9f\u00e9rences',
                                        'guardar preferencias', 'pr\u00e4ferenzen speichern',
                                        'enregistrer les choix', 'guardar opciones',
                                        'dismiss', 'ignorer', 'descartar', 'verwerfen',
                                        'continuer', 'continuar', 'continue', 'fortfahren',
                                        // Indonesian
                                        'terima', 'tolak', 'kustomisasi', 'simpan preferensi', 'lanjutkan', 'batalkan',
                                        // Turkish
                                        'kabul et', 'reddet', '\u00f6zelle\u015ftir', 'tercihleri kaydet',
                                        // Japanese
                                        '\u540c\u610f', '\u62d2\u5426', '\u30ab\u30b9\u30bf\u30de\u30a4\u30ba', '\u8a2d\u5b9a\u3092\u4fdd\u5b58',
                                        // Korean
                                        '\ub3d9\uc758', '\uac70\ubd80', '\uc0ac\uc6a9\uc790 \uc815\uc758', '\ud658\uacbd\uc124\uc815 \uc800\uc7a5',
                                        // Chinese
                                        '\u63a5\u53d7', '\u62d2\u7edd', '\u81ea\u5b9a\u4e49', '\u4fdd\u5b58\u504f\u597d\u8bbe\u7f6e',
                                        // Portuguese
                                        'aceitar', 'recusar', 'personalizar', 'salvar prefer\u00eancias',
                                        // Italian
                                        'accetta', 'declino', 'personalizza', 'salva preferenze', 'salva scelte', 'annulla', 'ignora', 'continua', 'cookie',
                                        // Polish
                                        'akceptuj', 'odrzu\u0107', 'personalizuj',
                                        // Dutch
                                        'accepteer', 'weiger', 'aanpassen', 'voorkeuren opslaan',
                                        // Russian
                                        '\u043f\u0440\u0438\u043d\u044f\u0442\u044c', '\u043e\u0442\u043a\u043b\u043e\u043d\u0438\u0442\u044c',
                                        // Arabic
                                        '\u0642\u0628\u0648\u0644', '\u0631\u0641\u0636'
                                    ];
                                    const isConsent = consentKeywords.some(k => allText.includes(k));
                                    if (!isConsent) return {action: 'no_consent'};
                                    
                                    const acceptWords = ['accept', 'accepter', 'aceptar', 'acceptieren', 'accetta', 'accettare', 'kabul et', 'yes', 's\u00ed', 'oui', 'ja', 'si', 'terima', 'agree', 'agree to', 'i agree', 'sim', 'aceitar', 'aceito', 'weiter', 'fortfahren', 'annahme'];
                                    const declineWords = ['decline', 'refuser', 'rechazar', 'ablehnen', 'declino', 'rifiuta', 'no', 'non', 'nein', 'reddet', 'nay', 'hay\u0131r', 'tolak', 'recusar', 'negar', 'verwerfen', 'abbrechen'];
                                    
                                    // Helper: dispatch proper MouseEvent to trigger React's event handlers
                                    function clickButton(btn) {
                                        const rect = btn.getBoundingClientRect();
                                        const x = rect.x + rect.width / 2;
                                        const y = rect.y + rect.height / 2;
                                        const opts = {bubbles: true, cancelable: true, view: window, clientX: x, clientY: y, button: 0};
                                        btn.dispatchEvent(new MouseEvent('mousedown', opts));
                                        btn.dispatchEvent(new MouseEvent('mouseup', opts));
                                        btn.dispatchEvent(new MouseEvent('click', opts));
                                    }
                                    
                                    // PRIORITY 1: Remove any element that contains both accept AND decline keywords
                                    // This is the most aggressive approach - removes the entire overlay from DOM
                                    // Don't check size - hidden overlays still block the page
                                    const containers = document.querySelectorAll('div, section, aside');
                                    for (const c of containers) {
                                        const containerText = (c.innerText || '').toLowerCase();
                                        const hasAccept = acceptWords.some(w => containerText.includes(w));
                                        const hasDecline = declineWords.some(w => containerText.includes(w));
                                        if (hasAccept && hasDecline && containerText.length < 2000) {
                                            // Make sure this is actually a consent overlay, not the main page
                                            c.remove();
                                            return {action: 'container_removed', reason: 'contains accept+decline'};
                                        }
                                    }
                                    
                                    // PRIORITY 2: Try to remove consent overlay by specific selectors
                                    const overlaySelectors = [
                                        '[data-testid="consent-banner"]',
                                        '[data-testid="cookie-banner"]',
                                        '[class*="consent-banner"]',
                                        '[class*="cookie-banner"]',
                                        '[class*="consent-overlay"]',
                                        '[class*="cookie-overlay"]',
                                    ];
                                    for (const sel of overlaySelectors) {
                                        const overlay = document.querySelector(sel);
                                        if (overlay) {
                                            overlay.remove();
                                            return {action: 'overlay_removed', selector: sel};
                                        }
                                    }
                                    
                                    // PRIORITY 3: Remove any dialog/role=dialog that contains consent keywords
                                    const dialogs = document.querySelectorAll('[role="dialog"], [class*="dialog"]');
                                    for (const d of dialogs) {
                                        const dialogText = (d.innerText || '').toLowerCase();
                                        const hasConsent = ['cookie', 'consent', 'privacy', 'preferences', 'accept', 'decline'].some(k => dialogText.includes(k));
                                        if (hasConsent) {
                                            d.remove();
                                            return {action: 'dialog_removed'};
                                        }
                                    }
                                    
                                    // PRIORITY 4: Click visible Accept button (only if visible)
                                    for (const b of allBtns) {
                                        const t = (b.textContent || '').trim().toLowerCase();
                                        if (acceptWords.includes(t) && b.offsetWidth > 0) {
                                            clickButton(b);
                                            return {action: 'clicked_accept_visible', text: t};
                                        }
                                    }
                                    
                                    // PRIORITY 5: Click Accept button even if not visible (MouseEvent)
                                    for (const b of allBtns) {
                                        const t = (b.textContent || '').trim().toLowerCase();
                                        if (acceptWords.includes(t)) {
                                            clickButton(b);
                                            return {action: 'clicked_accept', text: t, visible: false};
                                        }
                                    }
                                    
                                    // PRIORITY 6: Click Decline button
                                    for (const b of allBtns) {
                                        const t = (b.textContent || '').trim().toLowerCase();
                                        if (declineWords.includes(t)) {
                                            clickButton(b);
                                            return {action: 'clicked_decline', text: t, visible: b.offsetWidth > 0};
                                        }
                                    }
                                    
                                    return {action: 'no_action'};
                                }""")
                                if js_dismissed and js_dismissed.get('action') not in ['no_consent', 'no_action']:
                                    sp(f"  [+] Consent step {consent_step+1} handled: {js_dismissed}")
                                    dismissed = True
                                    time.sleep(1.5)
                                    # Check if consent overlay is still present
                                    still_consent = page.evaluate("""() => {
                                        const allBtns = document.querySelectorAll('button, [role="button"]');
                                        const texts = [];
                                        allBtns.forEach(b => texts.push((b.textContent || '').trim().toLowerCase()));
                                        const allText = texts.join('|');
                                        const consentKeywords = ['accepter', 'refuser', 'personnaliser', 'save preferences',
                                                                 'aceptar', 'rechazar', 'personalizar', 'guardar preferencias',
                                                                 'acceptieren', 'ablehnen', 'personalisieren', 'präferenzen speichern',
                                                                 'verwerfen', 'abbrechen', 'weiter', 'einstellungen speichern', 'datenschutzoptionen speichern',
                                                                 'terima', 'tolak', 'kustomisasi', 'simpan preferensi',
                                                                 'kabul et', 'reddet', 'özelleştir',
                                                                 'aceitar', 'recusar', 'personalizar',
                                                                 'accetta', 'declino', 'personalizza', 'salva preferenze',
                                                                 'akceptuj', 'odrzuć', 'personalizuj',
                                                                 'accepteer', 'weiger', 'aanpassen',
                                                                 '同意', '拒否', '동의를', '동의를',
                                                                 '接受', '拒绝', 'принять', 'отклонить'];
                                        return consentKeywords.some(k => allText.includes(k));
                                    }""") or False
                                    if not still_consent:
                                        sp("  [+] Consent overlay fully dismissed")
                                        break
                                else:
                                    break
                        except Exception as e:
                            sp(f"  [!] JS consent dismissal failed: {e}")
                    
                    time.sleep(3.0)
                    # If still blank after cookie handling, wait for SPA render
                    new_body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                    if len(new_body) < 50:
                        sp("  [*] Still blank after cookie accept, waiting for SPA...")
                        for rw in range(15):
                            time.sleep(2.0)
                            new_body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                            if len(new_body) > 50:
                                sp(f"  [+] SPA rendered ({len(new_body)} chars)")
                                break
            except Exception:
                pass
            
            # Now wait for name input to appear (up to 20 seconds)
            # Must handle blank SPA page, CCBA overlay, and cookie consent
            # Wait for name input to appear - check both input presence AND Continue button visibility
            # The form is rendered when either: a name input exists OR the Continue button (test-primary-button) is visible
            for w in range(30):
                try:
                    form_ready = page.evaluate("""() => {
                        // Check if Continue button is visible (form is rendered)
                        const continueBtn = document.querySelector('[data-testid="test-primary-button"]');
                        if (continueBtn && continueBtn.offsetWidth > 0) return 'continue_visible';
                        
                        // Check if name-related input exists
                        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                        for (const inp of inputs) {
                            if (!inp.disabled) {
                                const ph = (inp.placeholder || '').toLowerCase();
                                const nm = (inp.name || '').toLowerCase();
                                const id = (inp.id || '').toLowerCase();
                                const ac = (inp.autocomplete || '').toLowerCase();
                                // Skip inputs with @ in value (email field)
                                if (inp.value && inp.value.includes('@')) continue;
                                // Skip AWS CCC inputs
                                if (id.includes('awsccc') || nm.includes('awsccc')) continue;
                                // Check for name-related fields
                                if (ph.includes('name') || nm.includes('name') || id.includes('name')) return 'name_field';
                                // Check for autocomplete attributes
                                if (ac.includes('given-name') || ac.includes('family-name') || ac.includes('name')) return 'name_field';
                                // Check for formField pattern (AWS signup form)
                                if (id.startsWith('formfield')) return 'formfield';
                                // Check for text type inputs
                                if (inp.type === 'text') return 'text_input';
                            }
                        }
                        return null;
                    }""") or None
                    if form_ready:
                        sp(f"  [+] Name input found (form state: {form_ready})")
                        break
                except Exception:
                    pass
                time.sleep(1.0)
            
            time.sleep(random.randint(500,1200)/1000)

            # V6: Pre-interaction scroll + focus (anti-detection signal)
            try:
                page.mouse.wheel(0, random.randint(30, 80))
                time.sleep(0.5)
            except: pass
            
            # Name fill — JS direct value set with React-compatible events (PRIMARY strategy)
            # This must run FIRST because CloakBrowser's humanize pipeline doesn't work on hidden inputs
            # and the name input is often hidden by CSS (offsetWidth=0) behind the consent overlay
            name_filled = False
            
            # Strategy 1 (PRIMARY): Wait for name input to be in DOM, then JS direct value set
            # Use Playwright locator to wait for the input, then use JS to set value + dispatch React events
            selectors = [
                'input[autocomplete="given-name"]',
                'input[autocomplete="name"]',
                'input[placeholder*="name" i]',
                'input[name*="name" i]',
                'input[autocomplete*="name"]',
                'input[id*="name" i]',
                'input[aria-label*="name" i]',
                'input[placeholder*="first" i]',
                'input[placeholder*="last" i]',
                '#fullName', '#name', '#displayName',
                '#firstName', '#lastName',
            ]
            
            # First, wait for a name input to be in the DOM using Playwright locator
            # This ensures the input is actually rendered before we try to fill it
            name_locator = None
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=2000):
                        name_locator = loc
                        break
                except Exception:
                    pass
            
            # If no specific selector matched, try broader selectors
            if not name_locator:
                for sel in ['input[type="text"]:not([id*="awsccc"])', 'input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"])']:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=2000):
                            # Exclude email inputs
                            inp_type = loc.get_attribute('type') or 'text'
                            inp_value = loc.input_value() or ''
                            if inp_type != 'email' and '@' not in inp_value:
                                name_locator = loc
                                break
                    except Exception:
                        pass
            
            try:
                js_result = None
                # If Playwright locator found the input, use its id to target it via JS
                if name_locator:
                    input_id = name_locator.get_attribute('id') or ''
                    input_selector = name_locator._selector if hasattr(name_locator, '_selector') else ''
                    # Get the element's details via JS to confirm it exists
                    elem_info = page.evaluate("""(id) => {
                        const inp = id ? document.getElementById(id) : null;
                        if (!inp) return null;
                        return {id: inp.id, type: inp.type, value: inp.value, placeholder: inp.placeholder};
                    }""", input_id)
                    
                    if elem_info:
                        # Use the id to set the value via JS
                        js_result = page.evaluate("""(args) => {
                            const inp = document.getElementById(args.id);
                            if (!inp) return null;
                            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeSetter.call(inp, args.name);
                            inp.dispatchEvent(new Event('focus', {bubbles: true}));
                            inp.dispatchEvent(new Event('input', {bubbles: true, cancelable: true}));
                            inp.dispatchEvent(new Event('change', {bubbles: true, cancelable: true}));
                            inp.dispatchEvent(new Event('blur', {bubbles: true}));
                            return 'js_set_by_id:' + inp.id;
                        }""", {'id': input_id, 'name': name})
                        if js_result:
                            name_filled = True
                            sp(f"  [+] Name filled: {name} ({js_result})")
                    else:
                        # Input not found by id - use Playwright's locator.evaluate to set value directly
                        try:
                            js_result = name_locator.evaluate("""(inp, name) => {
                                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeSetter.call(inp, name);
                                inp.dispatchEvent(new Event('focus', {bubbles: true}));
                                inp.dispatchEvent(new Event('input', {bubbles: true, cancelable: true}));
                                inp.dispatchEvent(new Event('change', {bubbles: true, cancelable: true}));
                                inp.dispatchEvent(new Event('blur', {bubbles: true}));
                                return 'js_set_by_locator:' + (inp.placeholder || inp.id || inp.name || 'unknown');
                            }""", name)
                            if js_result:
                                name_filled = True
                                sp(f"  [+] Name filled: {name} ({js_result})")
                        except Exception as e:
                            sp(f"  [!] Locator evaluate failed: {e}")
                            js_result = None
                if js_result:
                    if isinstance(js_result, dict):
                        if js_result.get('result'):
                            name_filled = True
                            sp(f"  [+] Name filled: {name} ({js_result['result']})")
                            # Log debug info about all inputs found
                            debug_inputs = js_result.get('debug', [])
                            if debug_inputs:
                                sp(f"  [dbg] JS fill found {len(debug_inputs)} text inputs: {debug_inputs}")
                        else:
                            # JS fill failed - log what inputs were found
                            debug_inputs = js_result.get('debug', [])
                            if debug_inputs:
                                sp(f"  [!] JS fill failed - no matching input found. Inputs on page: {debug_inputs}")
                    else:
                        name_filled = True
                        sp(f"  [+] Name filled: {name} ({js_result})")
            except Exception as e:
                sp(f"  [!] JS name fill error: {e}")
            
            # Strategy 2: locator.click() + inp.type() which CloakBrowser intercepts
            # inp.type() goes through _humanized_type -> page.type() -> _human_keyboard_type
            # which uses the CloakBrowser human keyboard engine (per-char timing, realistic)
            # This is a secondary strategy in case JS fill doesn't work
            if not name_filled:
                for sel in selectors:
                    try:
                        inp = page.locator(sel).first
                        if inp.is_visible(timeout=1500):
                            # Exclude email inputs and inputs that already have a value (email field)
                            inp_type = inp.get_attribute('type') or 'text'
                            inp_value = inp.input_value() or ''
                            inp_autocomplete = inp.get_attribute('autocomplete') or ''
                            if inp_type == 'email' or '@' in inp_value:
                                continue  # This is the email field, skip it
                            inp.hover()
                            time.sleep(random.uniform(0.3, 0.6))
                            inp.click()
                            time.sleep(random.randint(600,1500)/1000)
                            # inp.type() goes through CloakBrowser humanize pipeline
                            inp.type(name)
                            name_filled = True
                            sp(f"  [+] Name filled: {name} (locator.type: {sel})")
                            break
                    except Exception:
                        pass
            
            # Strategy 3: inp.fill() which CloakBrowser also intercepts via _humanized_fill
            if not name_filled:
                for sel in selectors:
                    try:
                        inp = page.locator(sel).first
                        if inp.is_visible(timeout=1000):
                            # Exclude email inputs and inputs that already have a value
                            inp_type = inp.get_attribute('type') or 'text'
                            inp_value = inp.input_value() or ''
                            if inp_type == 'email' or '@' in inp_value:
                                continue  # This is the email field, skip it
                            inp.hover()
                            time.sleep(random.uniform(0.3, 0.6))
                            inp.click()
                            time.sleep(random.randint(600,1500)/1000)
                            # inp.fill() also goes through CloakBrowser humanize pipeline
                            inp.fill(name)
                            name_filled = True
                            sp(f"  [+] Name filled: {name} (locator.fill: {sel})")
                            break
                    except Exception:
                        pass
            
            # Strategy 4: human_type() via humanized keyboard - click field first then type
            if not name_filled:
                try:
                    for sel in selectors:
                        try:
                            inp = page.locator(sel).first
                            if inp.is_visible(timeout=1000):
                                inp.click()
                                time.sleep(random.randint(500,1000)/1000)
                                human_type(page, name)
                                name_filled = True
                                sp(f"  [+] Name filled: {name} (human_type)")
                                break
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # Strategy 3: human_type() via humanized keyboard - click field first then type
            if not name_filled:
                try:
                    for sel in selectors:
                        try:
                            inp = page.locator(sel).first
                            if inp.is_visible(timeout=1000):
                                inp.click()
                                time.sleep(random.randint(500,1000)/1000)
                                human_type(page, name)
                                name_filled = True
                                sp(f"  [+] Name filled: {name} (human_type)")
                                break
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # Strategy 4: JS fallback — minimal, just for edge cases
            if not name_filled:
                try:
                    # Get bounding box of first visible text input, click it, then use human_type
                    box = page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"])');
                        for (const inp of inputs) {
                            if (inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled) {
                                const id = (inp.id || '').toLowerCase();
                                const nm = (inp.name || '').toLowerCase();
                                if (id.includes('awsccc') || nm.includes('awsccc')) continue;
                                const r = inp.getBoundingClientRect();
                                return {x: r.x + r.width/2, y: r.y + r.height/2};
                            }
                        }
                        return null;
                    }""")
                    if box:
                        page.mouse.click(box['x'], box['y'])
                        time.sleep(random.randint(500,1000)/1000)
                        human_type(page, name)
                        name_filled = True
                        sp(f"  [+] Name filled: {name} (mouse click + human_type)")
                except Exception as e:
                    sp(f"  [!] Name fill all strategies failed: {e}")
            
            # Strategy 3: Screenshot and break if still stuck
            if not name_filled:
                # Diagnostic: print page URL and first 500 chars of body
                try:
                    page_url = page.url
                    body_preview = (page.evaluate("() => document.body?.innerText?.substring(0,1000)||''") or '')
                    sp(f"  [diag] URL: {page_url}")
                    sp(f"  [diag] Body preview: {body_preview[:500]}")
                except Exception as e:
                    sp(f"  [diag] Error reading page: {e}")
                take_screenshot(page, f"stuck_name_attempt_{attempt}")
                if attempt > 5:
                    sp("  [!] Breaking out of stuck loop - name field not found after 5+ attempts")
                    raise Exception("Name input field not found after multiple attempts")

            if name_filled:
                sp(f"  [+] Name filled: {name}")
                
                # V8: Verify the name is actually in the input value
                # inp.type() through CloakBrowser may not trigger React's onChange
                # Use JS to check the actual input value
                try:
                    actual_value = page.evaluate("""() => {
                        // Find the first name-related input that is NOT the email field
                        const allInps = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"])');
                        for (const inp of allInps) {
                            const ph = (inp.placeholder || '').toLowerCase();
                            const ac = (inp.autocomplete || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            const id = (inp.id || '').toLowerCase();
                            // Skip email inputs
                            if (inp.type === 'email' || inp.value.includes('@')) continue;
                            // Match name-related inputs (broader matching)
                            if (ph.includes('name') || ac.includes('name') || nm.includes('name') || id.includes('name') ||
                                ac.includes('given-name') || ph.includes('first') || ph.includes('last') ||
                                id.startsWith('formField')) {
                                return {value: inp.value, placeholder: inp.placeholder, autocomplete: inp.autocomplete, id: inp.id};
                            }
                        }
                        return null;
                    }""") or ''
                    if actual_value and isinstance(actual_value, dict) and actual_value.get('value'):
                        sp(f"  [+] Verified: input value = '{actual_value.get('value', '')}' (id={actual_value.get('id', '')}, placeholder={actual_value.get('placeholder', '')})")
                    elif actual_value:
                        sp(f"  [+] Verified: input found but empty: {actual_value}")
                    else:
                        sp("  [!] Name input not found or empty after fill")
                except Exception as e:
                    sp(f"  [!] Value check error: {e}")
                
                # V7b: Verify form actually rendered after consent dismissal
                # Check if the Continue button is visible (form is rendered)
                # Also check for collect-email-submit-button (AWS portal signup page)
                try:
                    continue_btn_visible = page.evaluate("""() => {
                        const btn = document.querySelector('[data-testid="test-primary-button"]');
                        if (btn && (btn.offsetWidth > 0 || btn.getClientRects().length > 0)) return 'test-primary-button';
                        // Check for AWS portal signup button
                        const emailBtn = document.querySelector('[data-testid="collect-email-submit-button"]');
                        if (emailBtn && (emailBtn.offsetWidth > 0 || emailBtn.getClientRects().length > 0)) return 'collect-email-submit-button';
                        // Check for any visible button with 'verify email' text
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            const t = (b.textContent || '').toLowerCase();
                            if (t.includes('verify email') && b.offsetWidth > 0 && !b.disabled) return 'verify-email-button';
                        }
                        return null;
                    }""") or False
                    if not continue_btn_visible:
                        sp("  [!] Continue button not visible - form not rendered yet, waiting...")
                        # Wait for form to render (Continue button visible)
                        try:
                            page.wait_for_selector('[data-testid="test-primary-button"], [data-testid="collect-email-submit-button"]', timeout=15000)
                            sp("  [+] Form rendered - Continue button visible")
                        except Exception:
                            sp("  [!] Form still not rendered after wait")
                    else:
                        sp(f"  [+] Form button found: {continue_btn_visible}")
                except Exception as e:
                    sp(f"  [!] Form render check error: {e}")
                
                # V7: Debug - check actual input value and button state
                try:
                    debug_info = page.evaluate("""(name) => {
                        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"])');
                        const results = [];
                        for (const inp of inputs) {
                            // Exclude email inputs (type=email or value contains @)
                            if (inp.type === 'email' || (inp.value && inp.value.includes('@'))) continue;
                            const ph = (inp.placeholder || '').toLowerCase();
                            const ac = (inp.autocomplete || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            const id = (inp.id || '').toLowerCase();
                            if (ph.includes('name') || ac.includes('name') || nm.includes('name') || id.includes('name')) {
                                results.push({
                                    value: inp.value,
                                    placeholder: inp.placeholder,
                                    autocomplete: inp.autocomplete,
                                    disabled: inp.disabled,
                                    type: inp.type,
                                    offsetWidth: inp.offsetWidth,
                                    visible: inp.offsetWidth > 0
                                });
                            }
                        }
                        const btn = document.querySelector('[data-testid="test-primary-button"]');
                        const emailBtn = document.querySelector('[data-testid="collect-email-submit-button"]');
                        const btnInfo = btn ? {
                            text: btn.textContent,
                            disabled: btn.disabled,
                            visible: btn.offsetWidth > 0
                        } : (emailBtn ? {
                            text: emailBtn.textContent,
                            disabled: emailBtn.disabled,
                            visible: emailBtn.offsetWidth > 0,
                            testid: 'collect-email-submit-button'
                        } : null);
                        return {inputs: results, continueBtn: btnInfo};
                    }""", name)
                    sp(f"  [dbg] Input state: {debug_info.get('inputs', [])}")
                    sp(f"  [dbg] Continue button: {debug_info.get('continueBtn')}")
                except Exception as e:
                    sp(f"  [!] Debug error: {e}")
                
                # V7: Force React state sync after name fill
                # inp.type() may not trigger React's onChange, so we dispatch events
                # Don't check offsetWidth - the input was already found by Playwright locator
                try:
                    page.evaluate("""(name) => {
                        // Find all text inputs (not hidden/password/email type) that are not disabled
                        // and have a placeholder containing 'name' or autocomplete containing 'name'
                        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"])');
                        for (const inp of inputs) {
                            if (inp.disabled) continue;
                            // Exclude email inputs (value contains @)
                            if (inp.value && inp.value.includes('@')) continue;
                            // Skip if already has the name value (set by JS fill)
                            if (inp.value === name) continue;
                            const ph = (inp.placeholder || '').toLowerCase();
                            const ac = (inp.autocomplete || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            const id = (inp.id || '').toLowerCase();
                            // Match name-related inputs
                            if (ph.includes('name') || ac.includes('name') || nm.includes('name') || id.includes('name')) {
                                // Set value using native setter (bypasses React's value getter)
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeInputValueSetter.call(inp, name);
                                // Dispatch events in correct order for React
                                inp.dispatchEvent(new Event('input', {bubbles: true, cancelable: true}));
                                inp.dispatchEvent(new Event('change', {bubbles: true, cancelable: true}));
                                // Also dispatch focus/blur to ensure React picks it up
                                inp.dispatchEvent(new Event('focus', {bubbles: true}));
                                inp.dispatchEvent(new Event('blur', {bubbles: true}));
                                return 'synced:' + (inp.placeholder || inp.id || 'unknown');
                            }
                        }
                        // If no name-matching input found, try all visible text inputs (exclude email)
                        for (const inp of inputs) {
                            if (!inp.disabled && inp.type === 'text' && !(inp.value && inp.value.includes('@'))) {
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeInputValueSetter.call(inp, name);
                                inp.dispatchEvent(new Event('input', {bubbles: true, cancelable: true}));
                                inp.dispatchEvent(new Event('change', {bubbles: true, cancelable: true}));
                                inp.dispatchEvent(new Event('focus', {bubbles: true}));
                                inp.dispatchEvent(new Event('blur', {bubbles: true}));
                                return 'synced_fallback:' + (inp.placeholder || inp.id || 'unknown');
                            }
                        }
                        return 'no_input_found';
                    }""", name)
                    sp("  [+] React state sync events dispatched")
                except Exception as e:
                    sp(f"  [!] React sync error: {e}")
                
                # Shorter thinking pause before submit (session expires on slow proxies)
                wait_time = random.randint(3000, 6000)
                sp(f"  [*] FWCIM humanizing: thinking pause {wait_time}ms...")
                time.sleep(wait_time/1000)

                # V7: Dismiss any consent overlay that may be blocking the Continue button
                # Handle multi-language (EN/FR/ES/DE) and multi-step consent overlays
                try:
                    for consent_pass in range(5):
                        consent_dismissed = page.evaluate("""() => {
                            const allBtns = document.querySelectorAll('button, [role="button"]');
                            const texts = [];
                            allBtns.forEach(b => texts.push((b.textContent || '').trim()));
                            const allText = texts.join('|').toLowerCase();
                            
                            // Check if this is a consent overlay (multi-language)
                            const consentKeywords = [
                                'accept', 'accepter', 'aceptar', 'acceptieren',
                                'refuser', 'refuse', 'rechazar', 'ablehnen',
                                'decline', 'personnaliser', 'personalizar', 'personalisieren',
                                'customize', 'save preferences', 'enregistrer les préférences',
                                'guardar preferencias', 'präferenzen speichern',
                                'enregistrer les choix', 'guardar opciones',
                                'dismiss', 'ignorer', 'descartar', 'verwerfen',
                                'continuer', 'continuar', 'continue', 'fortfahren',
                                // Italian
                                'accetta', 'declino', 'personalizza', 'salva preferenze',
                                // Indonesian
                                'terima', 'tolak', 'kustomisasi', 'simpan preferensi',
                                // Turkish
                                'kabul et', 'reddet', 'ozellestir',
                                // Portuguese
                                'aceitar', 'recusar', 'personalizar',
                                // Polish
                                'akceptuj', 'odrzuc',
                                // Dutch
                                'accepteer', 'weiger', 'aanpassen'
                            ];
                            const isConsent = consentKeywords.some(k => allText.includes(k));
                            if (!isConsent) return {action: 'no_consent'};
                            
                            // Check if consent overlay is blocking the form
                            const testPrimaryBtn = document.querySelector('[data-testid="test-primary-button"]');
                            const formVisible = testPrimaryBtn && testPrimaryBtn.offsetWidth > 0;
                            
                            // Strategy: Click Accept without checking offsetWidth
                            const acceptWords = ['accept', 'accepter', 'aceptar', 'acceptieren', 'accetta', 'kabul et', 'yes', 'sí', 'oui', 'ja', 'si', 'terima', 'aceitar', 'aceito', 'akceptuj', 'accepteer'];
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (acceptWords.includes(t)) {
                                    b.click();
                                    return {action: 'clicked_accept', text: t, formVisible};
                                }
                            }
                            // Try Save preferences
                            const saveWords = ['save preferences', 'enregistrer les préférences', 'guardar preferencias', 'präferenzen speichern', 'enregistrer les choix de confiance', 'tercihleri kaydet'];
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (saveWords.includes(t)) {
                                    b.click();
                                    return {action: 'clicked_save', text: t, formVisible};
                                }
                            }
                            // Try Decline
                            const declineWords = ['decline', 'refuser', 'rechazar', 'ablehnen', 'declino', 'rifiuta', 'no', 'non', 'nein', 'reddet', 'nay', 'hayır', 'tolak', 'recusar', 'negar', 'akceptuj', 'weiger'];
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (declineWords.includes(t)) {
                                    b.click();
                                    return {action: 'clicked_decline', text: t, formVisible};
                                }
                            }
                            // Try Dismiss
                            const dismissWords = ['dismiss', 'ignorer', 'descartar', 'verwerfen', 'yok say'];
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (dismissWords.includes(t)) {
                                    b.click();
                                    return {action: 'clicked_dismiss', text: t, formVisible};
                                }
                            }
                            // Try to remove consent overlay container
                            const overlaySelectors = ['[data-testid="consent-banner"]', '[data-testid="cookie-banner"]', '[role="dialog"]'];
                            for (const sel of overlaySelectors) {
                                const overlay = document.querySelector(sel);
                                if (overlay && overlay.offsetHeight > 50) {
                                    const overlayText = overlay.innerText.toLowerCase();
                                    if (['cookie', 'consent', 'privacy', 'preferences'].some(k => overlayText.includes(k))) {
                                        overlay.remove();
                                        return {action: 'overlay_removed', formVisible: true};
                                    }
                                }
                            }
                            // Remove containers with both accept and decline text
                            const containers = document.querySelectorAll('div, section, aside');
                            for (const c of containers) {
                                if (c.offsetHeight < 50 || c.offsetWidth < 50) continue;
                                const containerText = (c.innerText || '').toLowerCase();
                                if (acceptWords.some(w => containerText.includes(w)) && declineWords.some(w => containerText.includes(w))) {
                                    c.remove();
                                    return {action: 'container_removed', formVisible: true};
                                }
                            }
                            return {action: 'no_action', formVisible};
                        }""")
                        
                        if consent_dismissed and consent_dismissed.get('action') not in ['no_consent', 'no_action']:
                            sp(f"  [+] Consent pass {consent_pass+1}: {consent_dismissed}")
                            time.sleep(1.0)
                            # Check if consent overlay is still present
                            still_consent = page.evaluate("""() => {
                                const allBtns = document.querySelectorAll('button, [role="button"]');
                                const texts = [];
                                allBtns.forEach(b => texts.push((b.textContent || '').trim().toLowerCase()));
                                const allText = texts.join('|');
                                const consentKeywords = ['accepter', 'refuser', 'personnaliser', 'save preferences',
                                                         'aceptar', 'rechazar', 'personalizar', 'guardar preferencias',
                                                         'acceptieren', 'ablehnen', 'personalisieren', 'präferenzen speichern',
                                                         'verwerfen', 'abbrechen', 'weiter', 'einstellungen speichern', 'datenschutzoptionen speichern',
                                                         'terima', 'tolak', 'kustomisasi', 'simpan preferensi',
                                                         'kabul et', 'reddet', 'özelleştir',
                                                         'aceitar', 'recusar', 'personalizar'];
                                return consentKeywords.some(k => allText.includes(k));
                            }""") or False
                            if not still_consent:
                                sp("  [+] Consent overlay fully dismissed")
                                break
                        elif consent_dismissed and consent_dismissed.get('formVisible'):
                            # Form is already visible, no need to dismiss consent
                            sp("  [+] Form already visible, skipping consent dismissal")
                            break
                        else:
                            break
                except Exception as e:
                    sp(f"  [!] Consent dismissal error: {e}")
                
                # V8: Click Continue button — max 2 attempts to avoid infinite loop
                for w in range(2):
                    submitted = False
                    
                    # Wait for Continue button to appear (SPA may be slow)
                    try:
                        page.wait_for_selector('button:has-text("Continue")', timeout=8000)
                    except Exception:
                        pass
                    
                    # Also check for any visible button with Continue text
                    if w == 0:
                        try:
                            all_btns = page.evaluate("""() => {
                                const btns = document.querySelectorAll('button');
                                const info = [];
                                btns.forEach(b => {
                                    const t = (b.textContent || '').trim().substring(0, 30);
                                    const vis = b.offsetWidth > 0 && !b.disabled;
                                    const tid = b.getAttribute('data-testid') || '';
                                    info.push(`${t}|${vis}|${tid}`);
                                });
                                return info.join('||');
                            }""")
                            sp(f"  [dbg] Page buttons: {all_btns[:500]}")
                        except: pass
                    
                    try:
                        # Try data-testid first (most reliable)
                        testid_btn = page.locator('[data-testid="test-primary-button"]').first
                        if testid_btn.is_visible(timeout=2000):
                            # V5: Hover before clicking to signal human presence
                            testid_btn.hover()
                            time.sleep(random.randint(800,1500)/1000)
                            testid_btn.click(timeout=3000)
                            submitted = True
                            sp(f"  [+] Continue clicked (data-testid, humanized)")
                    except Exception:
                        pass
                    
                    if not submitted:
                        # Try collect-email-submit-button (AWS portal signup page)
                        try:
                            email_btn = page.locator('[data-testid="collect-email-submit-button"]').first
                            if email_btn.is_visible(timeout=2000):
                                email_btn.hover()
                                time.sleep(random.randint(800,1500)/1000)
                                email_btn.click(timeout=3000)
                                submitted = True
                                sp(f"  [+] Continue clicked (collect-email-submit-button, humanized)")
                        except Exception:
                            pass
                    
                    if not submitted:
                        try:
                            # Check if signup-next-button exists and is visible (after consent dismissal, it IS the form's button)
                            has_signup_next = page.evaluate("""() => {
                                const btn = document.querySelector('[data-testid="signup-next-button"]');
                                return btn && btn.offsetWidth > 0 ? true : false;
                            }""") or False
                            if has_signup_next:
                                sp("  [*] Using signup-next-button as Continue (consent already dismissed)")
                                try:
                                    signup_btn = page.locator('[data-testid="signup-next-button"]').first
                                    signup_btn.hover()
                                    time.sleep(random.randint(800,1500)/1000)
                                    signup_btn.click(timeout=3000)
                                    submitted = True
                                    sp(f"  [+] Continue clicked (signup-next-button, humanized)")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    
                    if not submitted:
                        try:
                            # Try native locator click - but exclude consent overlay buttons
                            # Use JS to find a 'continue' button that is NOT on the consent overlay
                            continue_btn_found = page.evaluate(r"""() => {
                                const btns = document.querySelectorAll('button');
                                for (const b of btns) {
                                    const t = (b.textContent || '').trim().toLowerCase();
                                    const tid = (b.dataset && b.dataset.testid) || '';
                                    // Skip consent overlay buttons (but NOT signup-next-button if it's the only continue button)
                                    if (tid === 'signup-email-change-button') continue;
                                    if (tid === 'cancel-button') continue;
                                    if (tid === 'test-signup-with-button-Google') continue;
                                    if (tid === 'test-signup-with-button-Apple') continue;
                                    if (tid === 'test-signup-with-button-GitHub') continue;
                                    if (tid === 'test-signup-with-button-Amazon') continue;
                                    // Match continue/next/verify email text
                                    if ((/continue|next/i.test(t) || /verify\s+email/i.test(t) || t.includes('verify email')) && b.offsetWidth > 0) {
                                        const r = b.getBoundingClientRect();
                                        return {x: r.x + r.width/2, y: r.y + r.height/2, text: t, testid: tid};
                                    }
                                }
                                return null;
                            }""")
                            if continue_btn_found:
                                page.mouse.click(continue_btn_found['x'], continue_btn_found['y'])
                                time.sleep(random.randint(500,1200)/1000)
                                submitted = True
                                sp(f"  [+] Continue clicked (JS mouse, testid={continue_btn_found.get('testid', '')})")
                        except Exception:
                            pass
                    
                    if not submitted:
                        # Fallback: JS click with scrollIntoView (but NOT on consent overlay)
                        try:
                            js_result = page.evaluate("""() => {
                                const btns = document.querySelectorAll('button');
                                // Consent overlay text patterns to avoid
                                const consentTexts = ['accepter', 'refuser', 'personnaliser', 'annuler', 
                                                      'enregistrer les préférences', 'enregistrer les choix',
                                                      'ignorer', 'save preferences', 'decline', 'customize',
                                                      'accept', 'dismiss'];
                                // Consent overlay testids to avoid
                                const consentTestids = ['signup-next-button', 'signup-email-change-button', 'cancel-button'];
                                for (const b of btns) {
                                    const t = (b.textContent || '').trim().toLowerCase();
                                    const tid = (b.dataset && b.dataset.testid) || '';
                                    // Skip consent overlay buttons by testid
                                    if (consentTestids.includes(tid)) continue;
                                    // Skip consent overlay buttons by text
                                    if (consentTexts.includes(t)) continue;
                                    // Skip if button is inside a consent/dialog overlay
                                    let parent = b.parentElement;
                                    let inConsentOverlay = false;
                                    while (parent) {
                                        const cls = (parent.className || '').toString().toLowerCase();
                                        if (cls.includes('consent') || cls.includes('cookie') || 
                                            cls.includes('dialog') || cls.includes('modal') ||
                                            parent.getAttribute('role') === 'dialog') {
                                            // Check if this dialog has consent-related buttons
                                            const dialogBtns = parent.querySelectorAll('button');
                                            let hasConsent = false;
                                            dialogBtns.forEach(db => {
                                                const dt = (db.textContent || '').trim().toLowerCase();
                                                if (consentTexts.includes(dt)) hasConsent = true;
                                            });
                                            if (hasConsent) {
                                                inConsentOverlay = true;
                                                break;
                                            }
                                        }
                                        parent = parent.parentElement;
                                    }
                                    if (inConsentOverlay) continue;
                                    
                                    if (b.offsetWidth > 0 && !b.disabled && (t.includes('continue') || t.includes('next'))) {
                                        b.scrollIntoView({block:'center', behavior:'instant'});
                                        b.click();
                                        return 'clicked:' + t;
                                    }
                                }
                                // Also try input[type=submit]
                                const subs = document.querySelectorAll('input[type="submit"]');
                                for (const s of subs) {
                                    if (s.offsetWidth > 0 && !s.disabled) {
                                        s.click();
                                        return 'clicked:submit';
                                    }
                                }
                                return '';
                            }""")
                            if js_result:
                                submitted = True
                                sp(f"  [+] Continue clicked (JS fallback: {js_result})")
                        except Exception as e:
                            sp(f"  [!] JS fallback error: {e}")
                    
                    if not submitted:
                        # Debug: print all buttons on page
                        try:
                            btn_debug = page.evaluate("""() => {
                                const btns = document.querySelectorAll('button, input[type="submit"], [role="button"]');
                                const info = [];
                                btns.forEach(b => {
                                    const t = (b.textContent || b.value || '').trim().substring(0, 50);
                                    const id = b.id || '';
                                    const cls = (b.className || '').toString().substring(0, 80);
                                    const testid = b.getAttribute('data-testid') || '';
                                    const vis = b.offsetWidth > 0 && !b.disabled;
                                    info.push(`btn: text="${t}" id="${id}" testid="${testid}" visible=${vis}`);
                                });
                                return info.join(' | ');
                            }""")
                            sp(f"  [dbg] Buttons on page: {btn_debug[:300]}")
                        except: pass
                        sp(f"  [!] Continue button not found (attempt {w+1})")
                    
                    # After clicking, also press Enter to ensure form submission
                    if submitted:
                        try:
                            page.keyboard.press("Enter")
                            time.sleep(0.5)
                        except: pass
                    
                    time.sleep(random.randint(2000,4000)/1000)
                    try:
                        ns = detect_state(page)
                        if ns not in ("signup-start", "unknown", "enter-email", "post-name-submit"):
                            sp(f"  [+] Transitioned to {ns}")
                            break
                        # If still signup-start, check if SPA is still loading (blank page)
                        body_len = 0
                        try:
                            body_len = len(page.evaluate("() => (document.body?.innerText||'').trim()") or '')
                        except: pass
                        # V8: If still on signup-start/post-name-submit after click, it's stuck
                        if ns == "post-name-submit":
                            sp("  [!] Still stuck post-name-submit after Continue click — force restart")
                            step_results['restart_full'] = True
                            break
                        if body_len == 0:
                            sp("  [*] SPA loading after name submit, waiting for OTP page...")
                            for spa_wait in range(15):
                                time.sleep(2.0)
                                try:
                                    new_body = page.evaluate("() => (document.body?.innerText||'').trim()") or ''
                                    # Also check for button presence (consent overlay might be visible)
                                    has_buttons = page.evaluate("""() => {
                                        const btns = document.querySelectorAll('button');
                                        let visibleCount = 0;
                                        btns.forEach(b => { if (b.offsetWidth > 0) visibleCount++; });
                                        return visibleCount;
                                    }""") or 0
                                    if len(new_body) > 20 or has_buttons > 5:
                                        if len(new_body) > 20:
                                            sp(f"  [+] SPA rendered ({len(new_body)} chars)")
                                        else:
                                            sp(f"  [+] Page has {has_buttons} buttons (may be consent overlay)")
                                            # Dismiss consent overlay if present
                                            try:
                                                page.evaluate("""() => {
                                                    const containers = document.querySelectorAll('div, section, aside');
                                                    for (const c of containers) {
                                                        if (c.offsetHeight < 50 || c.offsetWidth < 50) continue;
                                                        const text = (c.innerText || '').toLowerCase();
                                                        if (['cookie', 'consent', 'privacy', 'preferences', 'accept', 'decline', 'descartar', 'cancelar', 'verwerfen', 'abbrechen', 'ablehnen', 'weiter', 'einstellungen', 'datenschutz'].some(k => text.includes(k))) {
                                                            c.remove();
                                                            return 'dismissed';
                                                        }
                                                    }
                                                    return null;
                                                }""")
                                            except: pass
                                        break
                                except: pass
                            # Re-check state
                            ns2 = detect_state(page)
                            sp(f"  [post-SPA-wait] state={ns2}")
                            if ns2 != "signup-start":
                                sp(f"  [+] Transitioned to {ns2} after SPA wait")
                                break
                            else:
                                # Still signup-start after wait - session might be expired or proxy flagged
                                try:
                                    diag = page.evaluate("() => (document.body?.innerText||'').substring(0,300)") or ''
                                    if "sitzung abgelaufen" in diag.lower() or "session expired" in diag.lower():
                                        sp("  [!] Session expired after name submit")
                                        step_results['restart_email'] = True
                                        break
                                    # Check URL for error indicators
                                    current_url = page.url or ''
                                    if 'error' in current_url.lower() or 'chrome-error' in current_url.lower():
                                        sp("  [!] Error page detected after name submit")
                                        break
                                except: pass
                    except Exception:
                        pass
                continue

        elif state == "error":
            # ERR-837 or other AWS error — FWCIM-aware retry with longer cooldown
            body_text = ""
            try:
                body_text = (page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''") or "")
            except Exception:
                pass
            sp(f"  [!] Error state detected: {body_text[:100]}")
            if step_results.get('fill_name'):
                sp("  [*] ERR-837 after name submit — FWCIM cooldown + retry...")
                # FWCIM cooldown: much longer wait to let anti-bot reset (20-45 seconds)
                cooldown = random.uniform(20.0, 45.0)
                sp(f"  [*] Cooldown: {cooldown:.1f}s")
                time.sleep(cooldown)
                
                # Natural mouse movement during cooldown
                try:
                    page.mouse.move(random.randint(100, 900), random.randint(100, 700))
                    time.sleep(random.randint(500,1500)/1000)
                    page.mouse.move(random.randint(200, 800), random.randint(200, 500))
                    time.sleep(random.randint(500,1500)/1000)
                except Exception:
                    pass
                
                # Close error alert if present
                click_text(page, "Close", timeout=3000)
                time.sleep(random.randint(1000,2000)/1000)
                
                # Reload the page to clear any stale session state
                sp("  [*] Reloading page after ERR-837...")
                try:
                    page.goto(page.url, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(3.0, 5.0))
                except Exception:
                    pass
                
                # Try to find and fill name again using locator (humanized)
                try:
                    # V6: Pre-interaction scroll before retry fill
                    try:
                        page.mouse.wheel(0, random.randint(20, 60))
                        time.sleep(0.3)
                    except: pass
                    # Use locator-based fill for CloakBrowser humanize pipeline
                    name_filled = False
                    for sel in ['input[placeholder*="name" i]', 'input[id*="name" i]', 'input[name*="name" i]',
                                'input[autocomplete*="name"]', 'input[autocomplete="given-name"]']:
                        try:
                            inp = page.locator(sel).first
                            if inp.is_visible(timeout=2000):
                                inp.hover()
                                time.sleep(random.uniform(0.3, 0.6))
                                inp.click()
                                time.sleep(random.randint(500,1000)/1000)
                                inp.type(name)
                                name_filled = True
                                sp(f"  [+] Name refilled (locator.type: {sel})")
                                break
                        except Exception:
                            pass
                    
                    # JS fallback if locator fails
                    if not name_filled:
                        name_filled = page.evaluate("""(name) => {
                            const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"])');
                            for (const inp of inputs) {
                                if (inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled) {
                                    if (inp.value && inp.value.trim()) continue;
                                    const id = (inp.id || '').toLowerCase();
                                    const nm = (inp.name || '').toLowerCase();
                                    if (id.includes('awsccc') || nm.includes('awsccc')) continue;
                                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    nativeSetter.call(inp, name);
                                    inp.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: name}));
                                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                                    return true;
                                }
                            }
                            return false;
                        }""", name)
                    
                    if name_filled:
                        sp("  [+] Name refilled, FWCIM cooldown before submit...")
                        time.sleep(random.uniform(6.0,12.0))
                        
                        # Natural mouse movement before submit
                        try:
                            page.mouse.move(random.randint(300, 700), random.randint(300, 500))
                            time.sleep(random.randint(500,1500)/1000)
                        except Exception:
                            pass
                        
                        # Submit with data-testid (humanized locator)
                        submitted = False
                        try:
                            btn = page.locator('[data-testid="test-primary-button"]').first
                            if btn.is_visible(timeout=3000):
                                btn.click(timeout=3000)
                                submitted = True
                                sp("  [+] Continue clicked (retry, data-testid)")
                        except Exception:
                            pass
                        if not submitted:
                            click_text(page, "Continue", timeout=5000)
                            submitted = True
                            sp("  [+] Continue clicked (retry, text)")
                        time.sleep(random.uniform(6.0,12.0))
                except Exception as e:
                    sp(f"  [!] Retry error: {e}")
            else:
                sp("  [*] Error before name fill, restarting...")
                time.sleep(10.0)
            continue

        elif state == "enter-email":
            # Page went back to enter-email view (hash: #/signup/enter-email)
            sp("  [*] Page is on enter-email view, waiting for name page...")
            time.sleep(random.uniform(5.0,10.0))
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
                    step_results['fill_name'] = True
                    continue
            except Exception:
                pass
            continue

        elif state == "verify-otp":
            step_results['wait_otp'] = True
            step_results['fill_otp'] = True
            # Manual OTP — from env, or fall through to IMAP
            code = os.environ.get('MANUAL_OTP')
            if code:
                sp(f"  [*] Using manual OTP: {code}")
            elif mail_provider:
                # V8: Use mail provider for OTP
                sp(f"  [*] Polling OTP via {mail_provider.name} provider...")
                code = mail_provider.wait_otp(timeout=180, poll_interval=5)
                if code:
                    sp(f"  [+] OTP via {mail_provider.name}: {code}")
                else:
                    sp(f"  [!] {mail_provider.name} OTP timed out, trying IMAP fallback...")
                    code = poll_otp_imap(email, timeout=120)
            else:
                # IMAP with retry (3 attempts with progressive backoff)
                for attempt in range(3):
                    timeout = 1800 if attempt == 0 else 120
                    code = poll_otp_imap(email, timeout=timeout)
                    if code:
                        break
                    if attempt < 2:
                        sp(f"  [*] IMAP attempt {attempt+1} failed, retrying in 10s...")
                        time.sleep(10.0)
            if not code:
                sp("  [*] IMAP exhausted, trying visual Gmail as fallback...")
                code = poll_otp_gmail_visual(page, timeout=120)
            if code:
                # V9: Dismiss any consent overlay that may be blocking the OTP field
                # Multi-language consent overlay removal (including German)
                for consent_pass_otp in range(5):
                    try:
                        # Simplified OTP consent dismissal - avoid long JS with Unicode issues
                        consent_dismissed_otp = page.evaluate("""() => {
                            const allBtns = document.querySelectorAll('button, [role="button"]');
                            const texts = [];
                            allBtns.forEach(b => texts.push((b.textContent || '').trim().toLowerCase()));
                            const allText = texts.join('|');
                            const ckw = ['accept','accepter','aceptar','acceptieren','refuser','refuse',
                                'rechazar','ablehnen','decline','personnaliser','personalizar',
                                'customize','save preferences','guardar preferencias','dismiss',
                                'ignorer','descartar','verwerfen','continuer','continuar','continue',
                                'fortfahren','abbrechen','einstellungen speichern',
                                'datenschutzoptionen speichern','accetta','declino',
                                'terima','tolak','aceitar','recusar','akceptuj','odrzuc',
                                'accepteer','weiger','aanpassen'];
                            const isConsent = ckw.some(k => allText.includes(k));
                            if (!isConsent) return {action: 'no_consent'};
                            function clickButton(btn) {
                                btn.click();
                            }
                            const aw = ['accept','accepter','aceptar','acceptieren','accetta',
                                'yes','oui','ja','si','terima','agree','sim','aceitar','aceito',
                                'weiter','fortfahren','annahme'];
                            const dw = ['decline','refuser','rechazar','ablehnen','declino',
                                'rifiuta','no','non','nein','reddet','nay','tolak',
                                'recusar','negar','verwerfen','abbrechen'];
                            const cs = document.querySelectorAll('div, section, aside');
                            for (const c of cs) {
                                const ct = (c.innerText || '').toLowerCase();
                                if (ct.length < 2000 && aw.some(w => ct.includes(w)) && dw.some(w => ct.includes(w))) {
                                    c.remove(); return {action: 'container_removed', reason: 'contains accept+decline'};
                                }
                            }
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (aw.includes(t)) { clickButton(b); return {action: 'clicked_accept', text: t}; }
                            }
                            const sw = ['save preferences','guardar preferencias','einstellungen speichern',
                                'datenschutzoptionen speichern'];
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (sw.includes(t)) { clickButton(b); return {action: 'clicked_save', text: t}; }
                            }
                            for (const b of allBtns) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (dw.includes(t)) { clickButton(b); return {action: 'clicked_decline', text: t}; }
                            }
                            const ols = ['[data-testid="consent-banner"]','[data-testid="cookie-banner"]',
                                '[role="dialog"]','[aria-label*="cookie"]','[aria-label*="consent"]'];
                            for (const sel of ols) {
                                const ov = document.querySelector(sel);
                                if (ov) { ov.remove(); return {action: 'overlay_removed_by_selector', sel}; }
                            }
                            return {action: 'no_action'};
                        }""")
                        if consent_dismissed_otp and consent_dismissed_otp.get('action') not in ['no_consent', 'no_action']:
                            sp(f"  [+] OTP consent pass {consent_pass_otp+1}: {consent_dismissed_otp}")
                            time.sleep(1.5)
                            # Check if consent is still present (simplified to avoid syntax issues)
                            still_consent_otp = page.evaluate(r"""() => {
                                const allBtns = document.querySelectorAll('button, [role="button"]');
                                const texts = [];
                                allBtns.forEach(b => texts.push((b.textContent || '').trim().toLowerCase()));
                                const allText = texts.join('|');
                                const kws = ['accepter','refuser','personnaliser','save preferences','aceptar','rechazar',
                                    'acceptieren','ablehnen','ablehnen','verwerfen','abbrechen','weiter',
                                    'einstellungen','datenschutz','guardar preferencias','personalizar',
                                    'accetta','declino','personalizza','terima','tolak','kabul et',
                                    'aceitar','recusar','akceptuj','odrzuc','accepteer','weiger'];
                                return kws.some(k => allText.includes(k));
                            """) or False
                            if not still_consent_otp:
                                sp("  [+] Consent overlay fully dismissed on OTP page")
                                break
                    except Exception as e:
                        sp(f"  [!] OTP consent dismissal error: {e}")
                        break
                
                # JS-based OTP field detection — no Playwright .all() or .is_visible()
                otp_info = page.evaluate("""() => {
                    const vis = (el) => el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;
                    const splitBoxes = [];
                    const combInputs = [];
                    for (const el of document.querySelectorAll('input:not([type="hidden"]):not([type="password"])')) {
                        if (!vis(el)) continue;
                        if (el.maxLength === 1) {
                            splitBoxes.push({tag: el.tagName, idx: splitBoxes.length});
                        } else {
                            const p = (el.placeholder||'').toLowerCase();
                            const a = (el.getAttribute('aria-label')||'').toLowerCase();
                            const ac = (el.autocomplete||'').toLowerCase();
                            if (p.includes('code') || p.includes('digit') || p.includes('otp') || p.includes('chiffre')
                                || a.includes('code') || a.includes('verification') || ac === 'one-time-code') {
                                combInputs.push({id: el.id||'', name: el.name||'', ac: ac});
                            } else if (el.maxLength === 6 || el.inputMode === 'numeric') {
                                combInputs.push({id: el.id||'', name: el.name||'', ac: ac});
                            }
                        }
                    }
                    if (splitBoxes.length >= 6) return {type:'split', count: splitBoxes.length};
                    if (combInputs.length > 0) return {type:'combined', id: combInputs[0].id, name: combInputs[0].name};
                    return {type:'none'};
                }""")
                sp(f"  [+] OTP field type: {otp_info.get('type','?')}")

                if otp_info['type'] == 'split':
                    sp(f"  [+] OTP: split ({otp_info['count']} boxes)")
                    # Get bounding boxes via JS — no Playwright .all()/.is_visible()
                    boxes = page.evaluate("""() => {
                        const results = [];
                        for (const el of document.querySelectorAll('input:not([type="hidden"])')) {
                            if (el.maxLength !== 1) continue;
                            if (el.offsetWidth <= 0 || el.offsetHeight <= 0) continue;
                            const r = el.getBoundingClientRect();
                            results.push({x: r.x + r.width/2, y: r.y + r.height/2, w: r.width});
                        }
                        return results.slice(0, 6);
                    }""")
                    if not boxes:
                        sp("  [!] Split boxes not found via JS, waiting...")
                        time.sleep(5.0)
                    else:
                        for i, digit in enumerate(code):
                            if i < len(boxes):
                                b = boxes[i]
                                page.mouse.click(b['x'], b['y'], delay=random.randint(10, 30))
                                time.sleep(random.randint(100,300)/1000)
                                page.keyboard.type(digit, delay=random.randint(40, 100))
                                time.sleep(random.randint(80,200)/1000)
                        sp(f"  [+] OTP filled ({code})")
                        time.sleep(random.randint(500,1000)/1000)
                        page.keyboard.press('Tab')
                        time.sleep(random.uniform(3.0,5.0))

                elif otp_info['type'] == 'combined':
                    sel = f"#{otp_info['id']}" if otp_info['id'] else f'input[name="{otp_info["name"]}"]'
                    sp(f"  [+] OTP: combined ({sel})")
                    # JS visibility check instead of Playwright .is_visible()
                    visible = page.evaluate("""(sel) => {
                        const el = document.querySelector(sel);
                        return el && el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;
                    }""", sel)
                    if visible:
                        loc = page.locator(sel).first
                        human_click(page, loc)
                        time.sleep(random.randint(200,500)/1000)
                        human_type(page, code)
                        sp(f"  [+] OTP filled: {code}")
                        time.sleep(random.uniform(1.0,2.5))
                        clicked = (click_text(page, "Continue", timeout=3000) or \
                            click_text(page, "Verify", timeout=2000) or \
                            click_text(page, "Next", timeout=2000) or \
                            click_text(page, "Weiter", timeout=2000) or \
                            click_text(page, "Verifizieren", timeout=2000) or \
                            click_text(page, "Fortfahren", timeout=2000))
                        if not clicked:
                            clicked = page.evaluate("""() => {
                                const btns = document.querySelectorAll('button');
                                for (const b of btns) {
                                    if (b.offsetWidth > 0 && !b.disabled && b.offsetHeight > 0) {
                                        const t = (b.textContent || '').trim().toLowerCase();
                                        if (t && t !== 'cookie-einstellungen') {
                                            b.click(); return true;
                                        }
                                    }
                                }
                                return false;
                            """)
                        sp(f"  [+] OTP submitted" + ("" if clicked else " (no button clicked)"))
                    else:
                        sp("  [!] OTP field not visible")
                        time.sleep(5.0)
                else:
                    # Fallback: try any focused or first visible input
                    sp("  [!] OTP field not found by type, trying fallback selectors...")
                    fb_code = page.evaluate("""(code) => {
                        // Try inputmode="numeric" or autocomplete="one-time-code"
                        const sels = ['input[inputmode="numeric"]', 'input[autocomplete="one-time-code"]',
                                       'input[placeholder*="code" i]', 'input[aria-label*="code" i]'];
                        for (const sel of sels) {
                            const el = document.querySelector(sel);
                            if (el && el.offsetWidth > 0) {
                                el.focus();
                                el.value = '';
                                return {ok: true, sel: sel};
                            }
                        }
                        return {ok: false};
                    }""", code)
                    if fb_code.get('ok'):
                        sel = fb_code['sel']
                        sp(f"  [+] OTP fallback: {sel}")
                        loc = page.locator(sel).first
                        human_click(page, loc)
                        time.sleep(random.randint(200,500)/1000)
                        human_type(page, code)
                        sp(f"  [+] OTP filled: {code}")
                        time.sleep(random.uniform(1.0,2.5))
                        clicked = (click_text(page, "Continue", timeout=3000) or \
                            click_text(page, "Verify", timeout=2000) or \
                            click_text(page, "Next", timeout=2000) or \
                            click_text(page, "Weiter", timeout=2000) or \
                            click_text(page, "Verifizieren", timeout=2000) or \
                            click_text(page, "Fortfahren", timeout=2000))
                        if not clicked:
                            clicked = page.evaluate("""() => {
                                const btns = document.querySelectorAll('button');
                                for (const b of btns) {
                                    if (b.offsetWidth > 0 && !b.disabled && b.offsetHeight > 0) {
                                        const t = (b.textContent || '').trim().toLowerCase();
                                        if (t && t !== 'cookie-einstellungen') {
                                            b.click(); return true;
                                        }
                                    }
                                }
                                return false;
                            """)
                        sp(f"  [+] OTP submitted" + ("" if clicked else " (no button clicked)"))
                    else:
                        sp("  [!] No OTP input field found on page, waiting...")
                        time.sleep(10.0)

                sp("  [*] Waiting for OTP transition...")
                ns = wait_for_state_change(page, "verify-otp", timeout_sec=90)
                if ns: sp(f"  [+] Transitioned to {ns}")
                else: sp("  [!] Still on verify-otp after 90s")
            else:
                sp("  [!] No OTP received after all attempts")
                time.sleep(10.0)

        elif state == "password":
            step_results['fill_password'] = True
            # JS-based visibility check instead of Playwright .is_visible()
            pw_count = page.evaluate("""() => {
                let count = 0;
                for (const el of document.querySelectorAll('input[type="password"]')) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled) count++;
                }
                return count;
            }""")
            pw_filled = False
            if pw_count >= 1:
                pw_loc = page.locator('input[type="password"]').first
                human_click(page, pw_loc)
                time.sleep(random.randint(200,500)/1000)
                human_type(page, password)
                sp("  [+] Password filled")
                pw_filled = True

                if pw_count >= 2:
                    try:
                        time.sleep(random.uniform(1.0,2.0))
                        pw2 = page.locator('input[type="password"]').nth(1)
                        human_click(page, pw2)
                        time.sleep(random.randint(200,500)/1000)
                        human_type(page, password)
                        sp("  [+] Confirm password filled")
                    except Exception:
                        pass
            else:
                # Fallback: maybe password field has a different type or is hidden
                sp("  [!] Password field not found by type, trying fallback...")
                found = page.evaluate("""() => {
                    const sels = ['input[type="password"]', 'input[name*="password" i]',
                                   'input[name*="passwd" i]', 'input[autocomplete="new-password"]',
                                   'input[autocomplete="current-password"]'];
                    for (const sel of sels) {
                        const el = document.querySelector(sel);
                        if (el && el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled) {
                            return {ok: true, sel: sel};
                        }
                    }
                    return {ok: false};
                }""")
                if found.get('ok'):
                    sel = found['sel']
                    sp(f"  [+] Password fallback: {sel}")
                    loc = page.locator(sel).first
                    human_click(page, loc)
                    time.sleep(random.randint(200,500)/1000)
                    human_type(page, password)
                    sp("  [+] Password filled via fallback")
                    pw_filled = True
                else:
                    sp("  [!] No password field found on page")
                    time.sleep(5.0)

            # Submit password form — always executed regardless of which branch filled it
            if pw_filled:
                time.sleep(random.uniform(2.0,4.0))

                # Tick any terms/agreement checkboxes (not awsccc cookies)
                try:
                    checked_any = page.evaluate("""() => {
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
                    if checked_any:
                        sp(f"  [+] Ticked {checked_any} terms/agreement checkbox(es)")
                        time.sleep(random.randint(500,1000)/1000)
                except Exception:
                    pass

                step_results['create'] = True
                create = (click_text(page, "Create AWS Builder ID", timeout=3000) or \
                         click_text(page, "Create", timeout=2000) or \
                         click_text(page, "Continue", timeout=2000) or \
                         click_text(page, "Weiter", timeout=2000) or \
                         click_text(page, "Fortfahren", timeout=2000) or \
                         click_text(page, "Erstellen", timeout=2000))
                if not create:
                    # Fallback: click any visible button on the page
                    create = page.evaluate("""() => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            if (b.offsetWidth > 0 && !b.disabled && b.offsetHeight > 0) {
                                const t = (b.textContent || '').trim().toLowerCase();
                                if (t && t !== 'cookie-einstellungen' && t !== 'passwort anzeigen') {
                                    b.click(); return true;
                                }
                            }
                        }
                        return false;
                    """)
                if create:
                    sp("  [+] Account created!")
                else:
                    sp("  [!] No Create/Continue button found after password")

                time.sleep(random.uniform(2.0,4.0))

                step_results['redirect'] = True
                sp("  [*] Waiting for OAuth redirect (callback with auth code)...")
                # Wait for redirect to callback URL (localhost:3128) which captures auth_code
                for _ in range(20):
                    time.sleep(2.0)
                    if '127.0.0.1' in page.url or 'localhost' in page.url:
                        sp("  [+] Redirected to callback URL - auth_code should be captured")
                        break
                # Extra wait for callback server to process
                time.sleep(3.0)
                # First, sign in to trigger the consent page and capture auth_code
                sp("  [*] Signing in to capture auth code...")
                _signin_for_token_capture(page, email, password)
                time.sleep(3.0)
                # Exchange auth_code for tokens immediately
                if _exchange_auth_code_for_tokens():
                    sp("  [+] Tokens captured during account creation")
                # Now navigate to Kiro app for post-signup exploration
                if 'app.kiro.dev' not in page.url:
                    try:
                        page.goto("https://app.kiro.dev/", wait_until="domcontentloaded", timeout=30000)
                        time.sleep(5.0)
                        sp("  [+] Navigated to Kiro app for exploration")
                    except Exception:
                        pass
                for _ in range(10):
                    time.sleep(2.0)
                    if 'app.kiro.dev' in page.url:
                        sp("  [+] On Kiro app")
                        break

                step_results['explore'] = True
                post_start = time.time()
                post_duration = random.randint(30, 60)
                sp(f"  [*] Post-signup exploration: {post_duration}s...")
                while time.time() - post_start < post_duration:
                    human_scroll(page, random.choice([1, -1]))
                    time.sleep(random.uniform(1.5,4.0))
                    for sel in ['button:has-text("New")', 'button:has-text("Create")',
                                'a:has-text("New Project")', 'button:has-text("Start")',
                                'a:has-text("Dashboard")', 'button:has-text("Settings")']:
                        try:
                            loc = page.locator(sel).first
                            if loc.is_visible(timeout=1000):
                                human_click(page, loc)
                                time.sleep(random.uniform(2.0,4.0))
                                break
                        except Exception:
                            pass
                    try:
                        editor = page.locator('textarea, [contenteditable="true"], .cm-editor, .monaco-editor').first
                        if editor.is_visible(timeout=1000):
                            human_click(page, editor)
                            time.sleep(random.uniform(0.5,1.5))
                            human_type(page, random.choice([
                                'print("hello world")', 'const x = 42;', '// TODO: implement feature',
                                'def main():', 'import React from "react";',
                            ]), delay_range=(30, 120))
                            time.sleep(random.uniform(1.0,3.0))
                    except Exception:
                        pass
                    for sel in ['nav a', 'button:has-text("Menu")', '[role="menuitem"]', 'header button']:
                        try:
                            loc = page.locator(sel).first
                            if loc.is_visible(timeout=1000):
                                human_click(page, loc)
                                time.sleep(random.uniform(2.0,4.0))
                                break
                        except Exception:
                            pass
                    human_idle(page, 2, 5)

                return name, email, password

            time.sleep(3.0)

        elif state == "error":
            sp("  [!] Error page -- retrying...")
            take_screenshot(page, "error_page")
            time.sleep(5.0)
            try:
                page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=30000)
                human_wait_page_load(page)
            except Exception:
                pass
            attempt = 0

        elif state == "signin":
            # Signin page detected — we need to create a NEW account, not sign in
            # This means we landed on the existing-account signin page instead of signup
            # Navigate to the AWS signup page directly
            sp("  [!] On signin page but we need to SIGN UP. Redirecting to signup...")
            try:
                # Try to find a "Create a new AWS account" link
                signup_link = page.evaluate("""() => {
                    const links = document.querySelectorAll('a');
                    for (const a of links) {
                        const t = (a.textContent || '').toLowerCase();
                        if ((t.includes('create') && t.includes('account')) || t.includes('sign up') || t.includes('register')) {
                            return a.href;
                        }
                    }
                    for (const a of links) {
                        const t = (a.textContent || '').toLowerCase();
                        if (t.includes('new account') || t.includes('create account')) {
                            return a.href;
                        }
                    }
                    return null;
                }""")
                if signup_link:
                    sp(f"  [+] Found signup link: {signup_link}")
                    page.goto(signup_link, wait_until="commit", timeout=30000)
                    time.sleep(3)
                else:
                    sp("  [*] No signup link found, navigating to direct signup URL...")
                    page.goto("https://us-east-1.signin.aws/platform/d-9067642ac7/signup", wait_until="commit", timeout=30000)
                    time.sleep(3)
            except Exception as e:
                sp(f"  [!] Signup redirect failed: {e}")
                # Last resort: restart from Kiro
                try:
                    page.goto("https://app.kiro.dev/signin", wait_until="commit", timeout=30000)
                    time.sleep(3)
                except:
                    pass
            attempt = 0

        else:
            # Check for callback/localhost page (OIDC PKCE callback)
            page_url = page.url
            if "127.0.0.1" in page_url or "localhost" in page_url:
                try:
                    cb_body = (page.evaluate("() => (document.body?.innerText || '').toLowerCase().trim()") or '')
                    if 'registration complete' in cb_body or 'success' in cb_body or 'account created' in cb_body:
                        sp(f"  [!] ACCOUNT CREATION CONFIRMED via OIDC callback: {cb_body[:100]}")
                        take_screenshot(page, "registration_complete")
                        # Navigate to Kiro to complete the flow
                        try:
                            page.goto("https://app.kiro.dev", wait_until="domcontentloaded", timeout=30000)
                            human_wait_page_load(page)
                        except Exception:
                            pass
                        # Return success — account is created, skip remaining flow
                        return name, email, password
                except Exception:
                    pass
            
            time.sleep(4.0)
            if attempt > 40:
                sp(f"  [!] Giving up after {attempt} iterations")
                try:
                    page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=30000)
                    human_wait_page_load(page)
                    attempt = 0
                except Exception:
                    pass

    raise Exception("Account creation timed out")

# ══════════════════════════════════════════════════════════════════════════════
# Panel Operations
# ══════════════════════════════════════════════════════════════════════════════

def panel_login(page, panel_url, panel_pass):
    """Panel login via fetch API (no form interaction needed)."""
    sp("  [*] Panel login...")
    page.goto(panel_url, wait_until="domcontentloaded")
    time.sleep(3.0)
    current_url = page.url
    sp(f"  [*] Panel URL after nav: {current_url}")
    r = page.evaluate(f"""async () => {{
        try {{
            const r = await fetch('/api/auth/login', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{password:{json.dumps(panel_pass)}}})
            }});
            const text = await r.text();
            return {{ok: r.ok, status: r.status, body: text.substring(0, 200)}};
        }} catch(e) {{ return {{ok:false, error:e.message}}; }}
    }}""")
    sp(f"  [*] Panel login response: {r}")
    if r.get("ok"):
        sp("  [+] Panel logged in")
        page.goto(panel_url)
        time.sleep(2.0)
        return True
    sp(f"  [!] Panel login failed: {r}")
    return False

def panel_add_account(page, kiro_email, password, panel_url, mail_provider=None, refresh_token=""):
    """Add account to panel via device authorization flow (API-based).

    If refresh_token is provided, use the panel's import API directly (faster, no browser needed).
    Otherwise, fall back to the device auth browser flow.
    Uses the 9Router API: call /api/oauth/kiro/device-code to get the device auth URL,
    then open it and sign in with the Kiro account credentials.
    """
    # Strategy 1: Use import API with refresh_token (if available)
    if refresh_token:
        sp("  [*] Attempting panel import via refresh token API...")
        try:
            import_result = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('/api/oauth/kiro/import', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            refreshToken: '{refresh_token}',
                            region: 'us-east-1',
                            authMethod: 'builder-id',
                            startUrl: 'https://view.awsapps.com/start',
                            name: '{kiro_email}'
                        }})
                    }});
                    const text = await r.text();
                    return {{ok: r.ok, status: r.status, body: text.substring(0, 300)}};
                }} catch(e) {{ return {{ok: false, error: e.message}}; }}
            }}""")
            if import_result and import_result.get('ok'):
                sp(f"  [+] Account imported to panel via API! Status: {import_result.get('status')}")
                sp(f"  [+] Response: {import_result.get('body', '')[:100]}")
                return True
            else:
                sp(f"  [!] Import API failed: {import_result}")
                sp("  [*] Falling back to device auth flow...")
        except Exception as e:
            sp(f"  [!] Import API error: {e}")
            sp("  [*] Falling back to device auth flow...")

    # Strategy 1.5: Try to capture tokens via sign-in flow (if refresh_token not provided)
    if not refresh_token:
        sp("  [*] Attempting token capture via sign-in flow...")
        # Reset callback and OIDC client
        _callback_server["auth_code"] = ""
        if _register_oidc_client():
            # Navigate to Kiro sign-in with OIDC params
            signin_url = _oidc_client.get("signin_url", "")
            if signin_url:
                sp(f"  [*] Navigating to Kiro sign-in: {signin_url[:60]}...")
                try:
                    # Use a FRESH context to avoid existing session
                    sign_page = None
                    try:
                        sign_page = page.context.browser.new_page()
                        sp("  [+] Created fresh context for sign-in")
                    except Exception:
                        sign_page = page
                        sp("  [*] Using existing page for sign-in")
                    
                    sign_page.goto(signin_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(5.0)
                    # Click Builder ID
                    sign_page.evaluate("""() => {
                        document.querySelectorAll('button, a, div[role="button"]').forEach(el => {
                            const t = (el.innerText || '').toLowerCase();
                            if ((t.includes('builder id') || t.includes('builder')) && el.offsetWidth > 0) {
                                el.click();
                            }
                        });
                    }""")
                    sp("  [+] Builder ID clicked")
                    time.sleep(5.0)
                    # The OIDC authorize will redirect to AWS sign-in page
                    # Wait for it and fill credentials
                    for _ in range(15):
                        time.sleep(2.0)
                        url = sign_page.url
                        if 'signin.aws' in url or 'profile.aws' in url:
                            break
                    # Fill email
                    sign_page.evaluate(f"""() => {{
                        const inputs = document.querySelectorAll('input[type="email"], input[autocomplete="email"], input[placeholder*="email" i]');
                        for (const el of inputs) {{
                            if (el.offsetWidth > 0) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, '{kiro_email}');
                                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            }}
                        }}
                    }}""")
                    sp("  [+] Email filled")
                    time.sleep(1.0)
                    sign_page.evaluate("""() => {
                        document.querySelectorAll('button').forEach(b => {
                            const t = (b.innerText || '').toLowerCase();
                            if (t.includes('continue') || t.includes('next')) { b.click(); }
                        });
                    }""")
                    time.sleep(5.0)
                    # Fill password
                    sign_page.evaluate(f"""() => {{
                        const inputs = document.querySelectorAll('input[type="password"]');
                        for (const el of inputs) {{
                            if (el.offsetWidth > 0) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, '{password}');
                                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            }}
                        }}
                    }}""")
                    sp("  [+] Password filled")
                    time.sleep(1.0)
                    sign_page.evaluate("""() => {
                        document.querySelectorAll('button').forEach(b => {
                            const t = (b.innerText || '').toLowerCase();
                            if (t.includes('sign in') || t.includes('submit') || t.includes('continue')) { b.click(); }
                        });
                    }""")
                    sp("  [+] Sign in clicked")
                    time.sleep(5.0)
                    # Wait for OTP page
                    for _ in range(15):
                        time.sleep(2.0)
                        otp_visible = sign_page.evaluate("""() => {
                            const inputs = document.querySelectorAll('input[placeholder*="code" i], input[placeholder*="otp" i], input[maxlength="6"], input[type="text"][maxlength]');
                            for (const el of inputs) { if (el.offsetWidth > 0) return true; }
                            return false;
                        }""")
                        if otp_visible:
                            sp("  [+] OTP page detected")
                            break
                    # Get OTP from mail provider
                    if mail_provider and hasattr(mail_provider, 'fetch_otp'):
                        otp = mail_provider.fetch_otp(kiro_email)
                        if otp:
                            sp(f"  [+] OTP: {otp}")
                            sign_page.evaluate(f"""() => {{
                                const inputs = document.querySelectorAll('input[placeholder*="code" i], input[placeholder*="otp" i], input[maxlength="6"], input[type="text"][maxlength]');
                                for (const el of inputs) {{
                                    if (el.offsetWidth > 0) {{
                                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                        setter.call(el, '{otp}');
                                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                                    }}
                                }}
                            }}""")
                            time.sleep(1.0)
                            sign_page.evaluate("""() => {
                                document.querySelectorAll('button').forEach(b => {
                                    const t = (b.innerText || '').toLowerCase();
                                    if (t.includes('verify') || t.includes('continue') || t.includes('submit')) { b.click(); }
                                });
                            }""")
                            sp("  [+] OTP submitted")
                            time.sleep(5.0)
                    # Wait for consent page
                    for _ in range(25):
                        time.sleep(2.0)
                        body = sign_page.evaluate("() => (document.body?.innerText || '').toLowerCase()") or ""
                        if 'allow' in body and ('kiro' in body or 'access' in body):
                            sp("  [+] Consent page detected")
                            break
                        if _callback_server.get("auth_code"):
                            sp("  [+] Auth code already captured!")
                            break
                    # Click Allow
                    sign_page.evaluate("""() => {
                        document.querySelectorAll('button, a').forEach(el => {
                            const t = (el.innerText || '').toLowerCase();
                            if ((t.includes('allow') || t.includes('authorize')) && el.offsetWidth > 0) {
                                el.click();
                            }
                        });
                    }""")
                    sp("  [+] Allow clicked")
                    time.sleep(5.0)
                    # Wait for callback
                    for _ in range(15):
                        time.sleep(2.0)
                        if _callback_server.get("auth_code"):
                            sp("  [+] Auth code captured!")
                            break
                    # Exchange for tokens
                    if _callback_server.get("auth_code"):
                        if _exchange_auth_code_for_tokens():
                            refresh_token = _captured_tokens.get("refresh_token", "")
                            sp(f"  [+] Refresh token captured: {refresh_token[:20]}...")
                except Exception as e:
                    sp(f"  [!] Sign-in token capture error: {e}")
            else:
                sp("  [!] No signin URL available")
        else:
            sp("  [!] OIDC client registration failed")
    
    # Strategy 2: Use import API with refresh_token (if now available)
    if refresh_token:
        sp("  [*] Attempting panel import via refresh token API...")
        try:
            import_result = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('/api/oauth/kiro/import', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            refreshToken: '{refresh_token}',
                            region: 'us-east-1',
                            authMethod: 'builder-id',
                            startUrl: 'https://view.awsapps.com/start',
                            name: '{kiro_email}'
                        }})
                    }});
                    const text = await r.text();
                    return {{ok: r.ok, status: r.status, body: text.substring(0, 300)}};
                }} catch(e) {{ return {{ok: false, error: e.message}}; }}
            }}""")
            if import_result and import_result.get('ok'):
                sp(f"  [+] Account imported to panel via API! Status: {import_result.get('status')}")
                sp(f"  [+] Response: {import_result.get('body', '')[:100]}")
                return True
            else:
                sp(f"  [!] Import API failed: {import_result}")
                sp("  [*] Falling back to device auth flow...")
        except Exception as e:
            sp(f"  [!] Import API error: {e}")
            sp("  [*] Falling back to device auth flow...")
    sp("  [*] Adding account to panel Kiro provider via device auth (API)...")
    
    # Step 1: Get device code from the panel API
    sp("  [*] Getting device code from panel API...")
    device_code_data = None
    try:
        device_code_data = page.evaluate("""async () => {
            try {
                const r = await fetch('/api/oauth/kiro/device-code?start_url=https://view.awsapps.com/start&region=us-east-1&auth_method=idc');
                if (!r.ok) return {error: `HTTP ${r.status}`};
                return await r.json();
            } catch(e) {
                return {error: e.message};
            }
        }""")
        
        if device_code_data and 'error' in device_code_data:
            sp(f"  [!] Device code API error: {device_code_data['error']}")
            return False
        
        if not device_code_data or 'user_code' not in device_code_data:
            sp(f"  [!] No device code in response: {str(device_code_data)[:200]}")
            return False
        
        user_code = device_code_data.get('user_code', '')
        verification_uri = device_code_data.get('verification_uri_complete', '')
        sp(f"  [+] Device code obtained: user_code={user_code}")
        sp(f"  [+] Verification URL: {verification_uri[:80]}...")
        
    except Exception as e:
        sp(f"  [!] Device code API error: {e}")
        return False
    
    # Step 2: Open the AWS device authorization page (new incognito context to avoid cached sessions)
    sp("  [*] Opening AWS device auth page (fresh context)...")
    # Try to create a new browser context for isolation
    try:
        if page.context.browser:
            auth_context = page.context.browser.new_context(
                viewport=page.viewport_size or {"width": 1536, "height": 864},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
            )
            auth_page = auth_context.new_page()
        else:
            # Camoufox or other browser without browser attribute
            auth_context = page.context
            auth_page = auth_context.new_page()
    except Exception:
        # Fallback: same context, new page
        auth_context = page.context
        auth_page = auth_context.new_page()
    auth_page.set_default_timeout(60000)
    
    try:
        # Navigate to the device auth page
        goto_url = verification_uri or f"https://view.awsapps.com/start/#/device?user_code={user_code}"
        
        # Clear AWS session by navigating to AWS logout first, then clear cookies
        try:
            # Navigate to AWS SSO logout to kill any cached SSO session
            sp("  [*] Logging out of any cached AWS session...")
            auth_page.goto("https://view.awsapps.com/start/#/signout", wait_until="commit", timeout=15000)
            time.sleep(2.0)
            # Also try the API logout endpoint
            try:
                auth_page.evaluate("""async () => {
                    try { await fetch('https://view.awsapps.com/sso/logout', {method: 'POST', credentials: 'include'}); } catch(e) {}
                }""")
            except:
                pass
            time.sleep(1.0)
            
            # Now clear AWS cookies
            all_cookies = auth_context.cookies()
            panel_cookies = [c for c in all_cookies if 'sryze' in (c.get('domain', '') or '')]
            aws_cookies = [c for c in all_cookies if 'aws' in (c.get('domain', '') or '')]
            
            if aws_cookies:
                sp(f"  [*] Found {len(aws_cookies)} AWS cookies, clearing...")
                auth_context.clear_cookies()
                if panel_cookies:
                    for c in panel_cookies:
                        try:
                            auth_context.add_cookies([c])
                        except Exception:
                            pass
                    sp(f"  [+] Restored {len(panel_cookies)} panel cookies")
        except Exception as e:
            sp(f"  [*] AWS logout/cookie clear: {e}")
        
        # Navigate to the device auth page
        auth_page.goto(goto_url, wait_until="domcontentloaded", timeout=60000)
        # The device page is a SPA that redirects to signin.aws (Builder ID page)
        # It can take 10-30 seconds for the SPA to fully load and redirect.
        # Wait for the redirect or for the page to show content.
        sp("  [*] Waiting for device page SPA to load...")
        page_ready = False
        for i in range(20):  # up to 60 seconds
            time.sleep(3.0)
            url = auth_page.url
            # Check if redirected to signin.aws
            if 'signin.aws' in url or 'amazon.com' in url:
                sp(f"  [+] Redirected to sign-in page: {url[:80]}")
                page_ready = True
                break
            # Check if the page has meaningful content (SPA rendered)
            try:
                body_text = auth_page.evaluate("() => (document.body?.innerText || '').trim()")
                body_len = len(body_text) if body_text else 0
                if body_len > 50:
                    sp(f"  [+] Page content ready (len={body_len}), URL: {url[:80]}")
                    sp(f"  [+] Page text preview: {body_text[:100]}")
                    page_ready = True
                    break
            except Exception:
                pass  # Page might be navigating
            if i == 5:
                sp("  [*] Still waiting for SPA...")
        if not page_ready:
            sp(f"  [!] Page did not load within 60s. URL: {auth_page.url[:80]}")
            take_screenshot(auth_page, "aws_device_page_stuck")
        # Extra wait for SPA to fully render after redirect
        time.sleep(5.0)
        # Take screenshot
        take_screenshot(auth_page, "aws_device_page")
        
        # Check for errors
        body_text = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
        if "unable" in body_text.lower() and "error" in body_text.lower():
            sp(f"  [!] AWS error page: {body_text[:200]}")
            auth_page.close()
            return False
        
        # If the user code is already in the URL, we're good
        # If not, we need to enter it
        if user_code and user_code not in auth_page.url:
            # Look for the user code input field
            sp("  [*] Entering user code...")
            for _ in range(10):
                if auth_page.evaluate('() => !!document.querySelector(\'input[placeholder*="code"], input[name*="code"]\')'):
                    break
                time.sleep(2.0)
            
            # Fill user code
            code_filled = False
            try:
                code_input = auth_page.locator('input[placeholder*="code"], input[name*="code"]').first
                if code_input.is_visible(timeout=5000):
                    code_input.click()
                    time.sleep(0.3)
                    code_input.type(user_code, delay=random.randint(50, 100))
                    code_filled = True
                    sp("  [+] User code filled (native)")
            except Exception:
                pass
            
            if not code_filled:
                code_filled = auth_page.evaluate("""(code) => {
                    const inputs = document.querySelectorAll('input');
                    for (const inp of inputs) {
                        const ph = (inp.placeholder || '').toLowerCase();
                        if (ph.includes('code') && inp.offsetWidth > 0) {
                            inp.focus();
                            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            s.call(inp, code);
                            inp.dispatchEvent(new Event('input', {bubbles: true}));
                            inp.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }
                    }
                    return false;
                }""", user_code)
                if code_filled:
                    sp("  [+] User code filled (JS)")
            
            if code_filled:
                # Submit - press Enter or click Continue
                auth_page.keyboard.press("Enter")
                time.sleep(5.0)
        
        # Now handle the sign-in flow
        # First, check if we need to sign in with email
        sp("  [*] Checking for sign-in form...")
        
        # Wait for email input (AWS SSO uses input[type="text"] for email)
        email_visible = False
        for _ in range(15):
            email_visible = auth_page.evaluate("""() => {
                const vis = (el) => el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;
                // Check multiple selectors: email type, text type with email-related attributes
                const sels = [
                    'input[type="email"]',
                    'input[autocomplete="email"]',
                    'input[placeholder*="email" i]',
                    'input[aria-label*="email" i]',
                    'input[name*="email" i]',
                    'input[id*="email" i]',
                ];
                for (const sel of sels) {
                    for (const el of document.querySelectorAll(sel)) {
                        if (vis(el)) return true;
                    }
                }
                // AWS SSO device page: look for any visible text input that's not the user code
                for (const el of document.querySelectorAll('input:not([type="hidden"]):not([type="password"])')) {
                    if (!vis(el)) continue;
                    const ph = (el.placeholder || '').toLowerCase();
                    const nm = (el.name || '').toLowerCase();
                    const ac = (el.autocomplete || '').toLowerCase();
                    // If it's a text input that's not the user code input
                    if ((ph.includes('email') || nm.includes('email') || ac.includes('email')) ||
                        (ph.includes('user') || ph.includes('account') || nm.includes('user'))) {
                        return true;
                    }
                }
                // Fallback: any visible text input with autocomplete containing 'email' or name containing 'username'
                for (const el of document.querySelectorAll('input')) {
                    if (!vis(el)) continue;
                    if (el.type === 'text' && (el.autocomplete || '').toLowerCase().includes('email')) return true;
                    if ((el.name || '').toLowerCase().includes('username')) return true;
                }
                return false;
            }""")
            if email_visible:
                break
            time.sleep(3.0)
        
        if not email_visible:
            # Check if there's a cached session (Confirm button visible but no email form)
            has_confirm = auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t.includes('confirm and continue') && b.offsetWidth > 0) return true;
                }
                return false;
            }""")
            if has_confirm:
                sp("  [!] Cached AWS session detected - closing and retrying with fresh page...")
                auth_page.close()
                if auth_context != page.context:
                    try: auth_context.close()
                    except: pass
                # Create a fresh page (clears DOM state even in same context)
                if page.context.browser:
                    try:
                        auth_context = page.context.browser.new_context(
                            viewport=page.viewport_size or {"width": 1536, "height": 864},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            locale="en-US",
                            timezone_id="America/New_York",
                        )
                        auth_page = auth_context.new_page()
                    except Exception:
                        auth_context = page.context
                        auth_page = auth_context.new_page()
                else:
                    auth_context = page.context
                    auth_page = auth_context.new_page()
                auth_page.set_default_timeout(60000)
                # Navigate fresh
                auth_page.goto(goto_url, wait_until="domcontentloaded", timeout=60000)
                # Wait for SPA to load and redirect
                for _ in range(20):
                    time.sleep(3.0)
                    url = auth_page.url
                    if 'signin.aws' in url or 'amazon.com' in url:
                        break
                    try:
                        body_text = auth_page.evaluate("() => (document.body?.innerText || '').trim()")
                        if body_text and len(body_text) > 50:
                            break
                    except Exception:
                        pass
                time.sleep(3.0)
                # Re-check for email input (broader selectors)
                for _ in range(10):
                    email_visible = auth_page.evaluate("""() => {
                        const vis = (el) => el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;
                        for (const sel of ['input[type="email"]', 'input[autocomplete="email"]', 'input[placeholder*="email" i]', 'input[aria-label*="email" i]']) {
                            for (const el of document.querySelectorAll(sel)) {
                                if (vis(el)) return true;
                            }
                        }
                        // AWS SSO: text input for email
                        for (const el of document.querySelectorAll('input')) {
                            if (!vis(el)) continue;
                            if (el.type === 'text' && (el.autocomplete || '').toLowerCase().includes('email')) return true;
                            if ((el.name || '').toLowerCase().includes('username')) return true;
                            const ph = (el.placeholder || '').toLowerCase();
                            if (ph.includes('email') || ph.includes('account')) return true;
                        }
                        return false;
                    }""")
                    if email_visible:
                        break
                    time.sleep(3.0)
        
        if email_visible:
            # Fill email
            try:
                # Try multiple selectors for the email input (AWS SSO uses type="text")
                email_input = None
                for sel in ['input[type="email"]', 'input[autocomplete="email"]', 'input[placeholder*="email" i]', 'input[aria-label*="email" i]', 'input[name*="username" i]']:
                    try:
                        candidate = auth_page.locator(sel).first
                        if candidate.is_visible(timeout=3000):
                            email_input = candidate
                            break
                    except Exception:
                        pass
                if email_input is None:
                    # Fallback: find any visible text input that looks like an email field
                    email_input = auth_page.evaluate_handle("""() => {
                        const vis = (el) => el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;
                        for (const el of document.querySelectorAll('input:not([type="hidden"]):not([type="password"])')) {
                            if (!vis(el)) continue;
                            const ph = (el.placeholder || '').toLowerCase();
                            const nm = (el.name || '').toLowerCase();
                            const ac = (el.autocomplete || '').toLowerCase();
                            if (ph.includes('email') || nm.includes('email') || ac.includes('email') ||
                                ph.includes('account') || nm.includes('username') || nm.includes('user')) {
                                return el;
                            }
                        }
                        return null;
                    }""")
                if email_input is None:
                    sp("  [!] Email input not found with any selector")
                    return False
                # If it's an ElementHandle, wrap it
                if not hasattr(email_input, 'type'):
                    sp("  [!] Invalid email input handle")
                    return False
                email_input.wait_for(timeout=5000)
                email_input.click()
                time.sleep(0.3)
                email_input.type(kiro_email, delay=random.randint(50, 100))
                sp(f"  [+] Email filled: {kiro_email}")
                time.sleep(random.uniform(1.0, 2.0))
            except Exception:
                auth_page.evaluate("""(email) => {
                    const el = document.querySelector('input[type="email"]');
                    if (el) {
                        el.focus();
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(el, email);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""", kiro_email)
                sp(f"  [+] Email filled (JS): {kiro_email}")
            
            # Submit email - click Continue/Next or press Enter
            time.sleep(1.5)
            email_submitted = False
            try:
                submit_btn = auth_page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Next"), button:has-text("Sign in"]').first
                if submit_btn.is_visible(timeout=3000):
                    submit_btn.click(timeout=5000)
                    email_submitted = True
                    sp("  [+] Email submitted (native)")
            except Exception:
                pass
            
            if not email_submitted:
                auth_page.keyboard.press("Enter")
                sp("  [+] Email submitted (Enter)")
            
            time.sleep(8.0)
            take_screenshot(auth_page, "aws_after_email")
        
        # Check for OTP verification
        otp_needed = auth_page.evaluate("""() => {
            const body = (document.body?.innerText || '').toLowerCase();
            return body.includes('verify your identity') || body.includes('enter the 6-digit') || body.includes('verification code');
        }""")
        
        if otp_needed:
            sp("  [*] OTP verification required...")
            take_screenshot(auth_page, "aws_otp_needed")
            
            if mail_provider:
                otp_code = mail_provider.wait_otp(timeout=180, poll_interval=5)
                if otp_code:
                    sp(f"  [+] Got OTP: {otp_code}")
                    
                    otp_filled = False
                    try:
                        otp_input = auth_page.locator('input[name="otp"], input[name="code"], input[type="tel"], input[type="text"][autocomplete="one-time-code"], input[id*="otp"], input[id*="code"]').first
                        if otp_input.is_visible(timeout=5000):
                            otp_input.click()
                            time.sleep(0.3)
                            otp_input.type(otp_code, delay=random.randint(50, 100))
                            otp_filled = True
                            sp("  [+] OTP filled (native)")
                    except Exception:
                        pass
                    
                    if not otp_filled:
                        otp_filled = auth_page.evaluate("""(code) => {
                            const inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input[type="number"]');
                            for (const inp of inputs) {
                                if (inp.offsetWidth > 0 && !inp.disabled) {
                                    inp.focus();
                                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    s.call(inp, code);
                                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                                    return true;
                                }
                            }
                            return false;
                        }""", otp_code)
                        if otp_filled:
                            sp("  [+] OTP filled (JS)")
                    
                    if otp_filled:
                        time.sleep(1.0)
                        auth_page.keyboard.press("Enter")
                        sp("  [+] OTP submitted")
                        time.sleep(8.0)
                        take_screenshot(auth_page, "aws_after_otp")
                else:
                    sp("  [!] Failed to get OTP")
            else:
                sp("  [!] No mail provider for OTP")
        
        # Wait for password input (with longer timeout and page reload check)
        pw_visible = False
        for _ in range(30):
            # Check if password input is visible
            pw_visible = auth_page.evaluate('() => !!document.querySelector(\'input[type="password"]\')')
            if pw_visible:
                break
            # Also check if we've been redirected (e.g., to profile page)
            current_url = auth_page.url
            if 'profile.aws' in current_url or 'amazon.com' in current_url:
                # We've been redirected to the AWS profile page - this is the actual sign-in flow
                sp(f"  [*] On profile.aws page: {current_url[:80]}")
                time.sleep(3.0)
                # Check for password field on this page
                pw_visible = auth_page.evaluate('() => { const els = document.querySelectorAll("input[type=\\"password\\"]"); for (const e of els) { if (e.offsetWidth > 0 && e.offsetHeight > 0) return true; } return false; }')
                if pw_visible:
                    break
                body = auth_page.evaluate('() => (document.body?.innerText || "").toLowerCase()')
                # If page shows signup flow, try to navigate to sign-in
                if 'enter your name' in body or 'signup' in current_url.lower():
                    sp("  [*] On signup page - trying sign-in option...")
                    tried = auth_page.evaluate("""() => {
                        const links = document.querySelectorAll("a");
                        for (const a of links) {
                            const t = (a.textContent || "").trim().toLowerCase();
                            if (t.includes("sign in") || t.includes("sign-in") || t.includes("login")) {
                                a.click();
                                return true;
                            }
                        }
                        const btns = document.querySelectorAll("button");
                        for (const b of btns) {
                            const t = (b.textContent || "").trim().toLowerCase();
                            if (t === "change") {
                                b.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                    if tried:
                        sp("  [+] Clicked sign-in/change button")
                        time.sleep(3.0)
                # Continue waiting for password field
                continue
            time.sleep(3.0)
        
        if pw_visible:
            try:
                pw_input = auth_page.locator('input[type="password"]').first
                pw_input.wait_for(timeout=5000)
                pw_input.click()
                time.sleep(0.3)
                pw_input.type(password, delay=random.randint(50, 100))
                sp("  [+] Password filled")
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                auth_page.evaluate("""(pw) => {
                    const el = document.querySelector('input[type="password"]');
                    if (el) {
                        el.focus();
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(el, pw);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""", password)
                sp("  [+] Password filled (JS)")
            
            # Submit password
            time.sleep(1.5)
            pw_submitted = False
            try:
                submit_btn = auth_page.locator('button[type="submit"]').first
                if submit_btn.is_visible(timeout=3000):
                    submit_btn.click(timeout=5000)
                    pw_submitted = True
                    sp("  [+] Password submitted (native)")
            except Exception:
                pass
            
            if not pw_submitted:
                auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.offsetWidth > 0 && !b.disabled) {
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t.includes('sign') || t.includes('submit') || t.includes('login') || t.includes('allow') || t.includes('confirm')) {
                                b.click(); return true;
                            }
                        }
                    }
                    return false;
                }""")
                sp("  [+] Password submitted (JS)")
            
            if not pw_submitted:
                auth_page.keyboard.press("Enter")
                sp("  [+] Password submitted (Enter)")
            
            time.sleep(10.0)
            take_screenshot(auth_page, "aws_after_password")
        else:
            # Password field not found - try the full email+password flow on the current page
            sp("  [*] Password not visible, attempting email+password on current page...")
            take_screenshot(auth_page, "aws_before_retry")
            
            # Try to fill email on the current page (might be on profile.aws or signin.aws)
            current_url = auth_page.url
            sp(f"  [*] Current URL: {current_url[:100]}")
            
            # Try to find and fill email
            email_filled = False
            try:
                email_input = auth_page.locator('input[type="email"], input[autocomplete="email"], input[placeholder*="email" i], input[type="text"][autocomplete*="email" i]').first
                if email_input.is_visible(timeout=5000):
                    email_input.click()
                    time.sleep(0.3)
                    email_input.type(kiro_email, delay=random.randint(50, 100))
                    email_filled = True
                    sp("  [+] Email filled on current page")
            except Exception:
                pass
            
            if not email_filled:
                email_filled = auth_page.evaluate("""(email) => {
                    const inputs = document.querySelectorAll('input');
                    for (const el of inputs) {
                        if (el.offsetWidth > 0 && !el.disabled) {
                            const t = (el.type || 'text').toLowerCase();
                            const ac = (el.autocomplete || '').toLowerCase();
                            const ph = (el.placeholder || '').toLowerCase();
                            if (t === 'email' || ac.includes('email') || ph.includes('email')) {
                                el.focus();
                                const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                s.call(el, email);
                                el.dispatchEvent(new Event('input', {bubbles: true}));
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                                return true;
                            }
                        }
                    }
                    return false;
                }""", kiro_email)
                if email_filled:
                    sp("  [+] Email filled (JS) on current page")
            
            if email_filled:
                time.sleep(1.0)
                # Submit email
                try:
                    submit_btn = auth_page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Next")').first
                    if submit_btn.is_visible(timeout=3000):
                        submit_btn.click(timeout=5000)
                        sp("  [+] Email submitted on current page")
                except Exception:
                    auth_page.keyboard.press("Enter")
                    sp("  [+] Email submitted (Enter) on current page")
                time.sleep(5.0)
            
            # Now wait for password field
            for _ in range(10):
                time.sleep(2.0)
                pw_visible = auth_page.evaluate('() => { const els = document.querySelectorAll("input[type=\\"password\\"]"); for (const e of els) { if (e.offsetWidth > 0 && e.offsetHeight > 0) return true; } return false; }')
                if pw_visible:
                    break
            
            if pw_visible:
                try:
                    pw_input = auth_page.locator('input[type="password"]').first
                    pw_input.click()
                    time.sleep(0.3)
                    pw_input.type(password, delay=random.randint(50, 100))
                    sp("  [+] Password filled (retry)")
                    time.sleep(1.5)
                    submit_btn = auth_page.locator('button[type="submit"], button:has-text("Sign in")').first
                    if submit_btn.is_visible(timeout=3000):
                        submit_btn.click(timeout=5000)
                        sp("  [+] Password submitted (retry)")
                except Exception:
                    auth_page.keyboard.press("Enter")
                    sp("  [+] Password submitted (Enter, retry)")
                time.sleep(10.0)
                take_screenshot(auth_page, "aws_after_password_retry")
        
        # Wait for Allow/Authorize/Confirm button
        sp("  [*] Waiting for Allow/Authorize button...")
        confirm_clicked = False
        
        for _ in range(15):
            try:
                allow_btn = auth_page.locator('button:has-text("Allow"), button:has-text("Authorize"), button:has-text("Confirm and continue")').first
                if allow_btn.is_visible(timeout=2000):
                    allow_btn.click(timeout=5000)
                    sp(f"  [+] Clicked: Allow/Confirm (native)")
                    confirm_clicked = True
                    time.sleep(8.0)
                    break
            except Exception:
                pass
            
            if not confirm_clicked:
                clicked_text = auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.offsetWidth > 0 && !b.disabled) {
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t.includes('allow') || t.includes('authorize') || t.includes('confirm and continue')) {
                                b.click();
                                return b.textContent.trim();
                            }
                        }
                    }
                    return '';
                }""")
                if clicked_text:
                    sp(f"  [+] Clicked: {clicked_text} (JS)")
                    confirm_clicked = True
                    time.sleep(8.0)
                    break
            
            time.sleep(2.0)
        
        if not confirm_clicked:
            # Try clicking any button that's not deny/cancel
            auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled) {
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('deny') || t.includes('cancel') || t.includes('close') || t.includes('reject')) continue;
                        b.click(); return true;
                    }
                }
                return false;
            }""")
            sp("  [+] Clicked first available button")
            time.sleep(8.0)
        
        # Wait for panel to detect the authorization
        # The panel polls the AWS SSO token endpoint after the user confirms on AWS.
        # Once confirmed, the panel stores the clientId/clientSecret automatically.
        sp("  [*] Waiting for panel to detect authorization...")
        auth_detected = False
        
        # Get initial provider count for comparison
        initial_count = page.evaluate("""async () => {
            try {
                const r = await fetch('/api/providers', {credentials: 'include'});
                if (!r.ok) return -1;
                const data = await r.json();
                return Array.isArray(data) ? data.length : -1;
            } catch(e) { return -1; }
        }""")
        sp(f"  [*] Initial provider count: {initial_count}")
        
        for _ in range(60):
            time.sleep(2.0)
            
            # Check the main page for success indicators
            page_text = page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''")
            if any(w in page_text.lower() for w in ['success', 'connected', 'authorized', 'account added', 'added successfully']):
                sp(f"  [+] Panel shows success: {page_text[:150]}")
                auth_detected = True
                break
            
            # Check via API if the provider count increased
            current_count = page.evaluate("""async () => {
                try {
                    const r = await fetch('/api/providers', {credentials: 'include'});
                    if (!r.ok) return -1;
                    const data = await r.json();
                    return Array.isArray(data) ? data.length : -1;
                } catch(e) { return -1; }
            }""")
            
            if initial_count >= 0 and current_count > initial_count:
                sp(f"  [+] Panel provider count increased: {initial_count} -> {current_count}")
                auth_detected = True
                break
            
            # Check if the auth page shows success/redirect
            auth_body = auth_page.evaluate("() => document.body?.innerText?.substring(0, 300) || ''")
            auth_url = auth_page.url
            if any(w in auth_body.lower() for w in ['success', 'authorized', 'connected', 'code accepted']) or \
               'dashboard' in auth_url.lower() or auth_url.endswith('/#/'):
                if not auth_body.lower().strip():
                    # Empty page after redirect = success
                    sp(f"  [+] Auth page redirected (empty/dashboard)")
                    auth_detected = True
                    break
            
            # Check if AWS redirected away from the consent page
            if 'consent' not in auth_url and 'device' not in auth_url and _ > 5:
                sp(f"  [+] Auth page redirected to: {auth_url[:80]}")
                auth_detected = True
                break
            
            if _ % 10 == 0:
                sp(f"  [*] Still waiting... auth_url: {auth_url[:80]}")
        
        auth_page.close()
        try: auth_context.close()
        except: pass
        return auth_detected
        
    except Exception as e:
        sp(f"  [!] Device auth error: {e}")
        try: auth_page.close()
        except: pass
        try: auth_context.close()
        except: pass
        return False


def save_creds(email, password, panel_url, name=""):
    fe = CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not fe: w.writerow(["Name","Email","Password","Panel","Timestamp"])
        w.writerow([name, email, password, panel_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    sp(f"  [+] Saved to {CSV_FILE}")

def print_result_summary(config, proxy_ip, proxy_org, ban_step, duration, success, db):
    """Print a formatted result summary after each account."""
    icon = "✅" if success else ("❌" if ban_step else "⚠️")
    result_text = "Survived" if success else ("Banned" if ban_step else "Error")
    sp(f"\n  ┌─ RESULT {'─' * 36}")
    sp(f"  │ {icon} {result_text}")
    sp(f"  │ Proxy: {proxy_ip or '?'} ({proxy_org[:40] if proxy_org else '?'})")
    sp(f"  │ OS: {config['os']} | Viewport: {config['viewport']['width']}x{config['viewport']['height']}")
    sp(f"  │ Preset: #{config['preset_idx']} | Profile: {config['profile_type']}")
    sp(f"  │ Domain: {config.get('domain', '?')} | Time: {duration:.0f}s")
    if ban_step:
        sp(f"  │ Failed at: {ban_step}")
    if db:
        stats = db.get_stats()
        sp(f"  │ DB: {stats['total']} attempts, {stats['survived']} survived, {stats['banned']} banned, {stats['active_configs']}/{stats['total_configs']} configs active")
    sp(f"  └{'─' * 44}")

# ══════════════════════════════════════════════════════════════════════════════
# Run One Cycle
# ══════════════════════════════════════════════════════════════════════════════

def run_one(panel_url, panel_pass, domain, proxy_country, headless, config, db, no_proxy=False, mail_provider=None, extra_panels=None):
    """Run one account creation cycle with config rotation and step tracking.
    
    V8: Accepts optional mail_provider for disposable email signup.
    V9: Accepts extra_panels — list of (url, pass) tuples to add the same account to.
    """
    geo = COUNTRY_LOCALE.get(proxy_country, COUNTRY_LOCALE['us'])
    proxy_ip = None
    proxy_org = None
    profile_dir = None
    proxy = None
    browser = None

    if not no_proxy:
        # Phase 1 proxy — auto-retry on datacenter (curl check supports HTTP+SOCKS5)
        import subprocess, base64
        for retry in range(8):
            candidate = get_proxy_fallback(proxy_country)
            if not candidate or not candidate.get('server'):
                sp(f"  [!] No proxy candidate on attempt {retry+1}")
                continue
            sp(f"  Proxy attempt {retry+1}/8: {candidate.get('username','?')}")

            ok = False; info = None
            try:
                # Use curl for proxy check — supports both HTTP and SOCKS5
                proxy_url = candidate['server']
                username = candidate.get('username', '')
                password = candidate.get('password', '')
                # For SOCKS5, embed credentials in the URL
                if proxy_url.startswith('socks5'):
                    full_proxy_url = f"socks5://{username}:{password}@{proxy_url.split('://')[1]}" if '://' in proxy_url else f"socks5://{username}:{password}@{proxy_url}"
                    curl_cmd = ['curl', '-s', '--proxy', full_proxy_url, '--max-time', '15', 'https://api.ipify.org?format=json']
                else:
                    user_pass = f"{username}:{password}"
                    curl_cmd = ['curl', '-s', '--proxy-user', user_pass, '--proxy', proxy_url, '--max-time', '15', 'https://api.ipify.org?format=json']
                result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=20)
                body = result.stdout.strip()
                data = json.loads(body)
                ip = data.get('ip', '?')
                proxy_ip = ip
                # Check IP reputation via ip-api
                import requests
                r = requests.get(f'http://ip-api.com/json/{ip}', timeout=10)
                ip_info = r.json()
                org = (ip_info.get('org') or ip_info.get('isp') or '').lower()
                proxy_org = org
                sp(f"    [i] Proxy IP: {ip} | Org: {org[:60]}")
                datacenter = any(bad in org for bad in DATACENTER_ORGS)
                if not datacenter:
                    ok = True
                    proxy = candidate
                    proxy_ip = ip
                    proxy_org = org
                    sp(f"  [+] Proxy OK: {candidate.get('username','?')}")
                    break
                else:
                    sp(f"    [!] DATACENTER IP DETECTED — retrying...")
            except Exception as e:
                sp(f"  [!] Proxy test failed: {e}")

        if not proxy:
            sp("  [!] No valid proxy found after 8 retries!")
            cf = dict(config); cf['domain'] = domain or '?'
            db.record_attempt("no_proxy", "?", "?", cf, "error", "no_proxy", "No valid proxy found", 0)
            return None, None, None, None, None
    else:
        # No-proxy mode — direct connection (e.g., Opera VPN)
        import urllib.request
        try:
            req = urllib.request.Request("https://ipinfo.io/json")
            resp = urllib.request.urlopen(req, timeout=15)
            body = resp.read().decode()
            info = json.loads(body)
            proxy_ip = info.get("ip", "?")
            proxy_org = (info.get("org") or "").lower()
            sp(f"  [i] Direct IP: {proxy_ip} | Org: {proxy_org[:60]}")
        except Exception as e:
            sp(f"  [!] IP check failed (non-fatal): {e}")
            proxy_ip = "?"
            proxy_org = "?"

    profile_dir = os.path.join(BASE_DIR, "browser_profile")
    os.makedirs(profile_dir, exist_ok=True)

    # Clean stale browser locks before launch
    for _lock in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        _lp = os.path.join(profile_dir, _lock)
        if os.path.exists(_lp):
            try: os.remove(_lp)
            except: pass

    sp(f"  Proxy: {'DIRECT' if no_proxy else candidate.get('username','?')} | IP: {proxy_ip}")
    sp(f"  Headless: {headless}")
    sp(f"  OS: {config['os']} | Profile: {config['profile_type']}")

    start_time = time.time()
    step_results = {}
    ban_step = None
    success = False
    name = None; email = None; pwd = None
    browser = None; page = None

    # Single browser architecture — same proxy/fingerprint for entire lifecycle
    # Add localhost bypass so panel (localhost:20128) is reachable without proxy
    browser_proxy = None
    if proxy:
        browser_proxy = dict(proxy)
        browser_proxy['bypass'] = 'localhost,127.0.0.1,::1'

    try:
        try:
            from cloakbrowser import launch_persistent_context
        except ImportError:
            _cb = str(CLOAKBROWSER_DIR)
            if _cb not in sys.path:
                sys.path.insert(0, _cb)
            from cloakbrowser import launch_persistent_context
        # CloakBrowser with FWCIM-compatible config
        # geoip=True: matches timezone+locale to proxy exit IP (critical for FWCIM)
        # human_preset="careful": slower, more deliberate interactions
        # --fingerprint-noise=false: prevents FWCIM tampering detection
        # --fingerprint-webrtc-ip=auto: WebRTC fingerprint matches proxy IP
        # V5 Fix: Clean User-Agent to bypass FWCIM fingerprint detection
        clean_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        
        # Build args based on mode
        launch_args = [
            "--fingerprint-noise=false",
            "--disable-blink-features=AutomationControlled",
            "--fingerprint-storage-quota=5000",
        ]
        # Only add WebRTC flag when using proxy (it fails on no-proxy)
        if not no_proxy:
            launch_args.append("--fingerprint-webrtc-ip=auto")
        
        # First run: add --disable-http2 to warm up cookies (HTTP/2 can trigger anti-bot)
        first_run_path = os.path.join(profile_dir, ".first_run_done")
        if not os.path.exists(first_run_path):
            launch_args.append("--disable-http2")
            sp("  [i] First run: --disable-http2 for cookie warmup")

        # Fix Python 3.10+: clear asyncio loop before Playwright sync API
        try:
            import asyncio
            asyncio.set_event_loop(None)
        except Exception:
            pass
        # Nuclear patch: replace Playwright's __enter__ to always use a fresh loop
        try:
            import playwright.sync_api._context_manager as _pw_cm
            def _safe_enter(self):
                self._loop = asyncio.new_event_loop()
                self._own_loop = True
                asyncio.set_event_loop(self._loop)
                # Bypass _check_running to allow greenlet switching with asyncio
                self._loop._check_running = lambda: None
                from greenlet import greenlet
                from playwright._impl._connection import Connection, ChannelOwner
                from playwright._impl._object_factory import create_remote_object
                from playwright._impl._transport import PipeTransport
                from playwright._impl._playwright import Playwright
                from playwright._impl._greenlets import MainGreenlet
                from playwright.sync_api._generated import Playwright as SyncPlaywright
                from typing import cast
                def greenlet_main():
                    self._loop.run_until_complete(self._connection.run_as_sync())
                dispatcher_fiber = MainGreenlet(greenlet_main)
                self._connection = Connection(
                    dispatcher_fiber, create_remote_object,
                    PipeTransport(self._loop), self._loop,
                )
                g_self = greenlet.getcurrent()
                def callback_wrapper(channel_owner):
                    playwright_impl = cast(Playwright, channel_owner)
                    self._playwright = SyncPlaywright(playwright_impl)
                    g_self.switch()
                self._connection.call_on_object_with_known_name("Playwright", callback_wrapper)
                dispatcher_fiber.switch()
                playwright = self._playwright
                playwright.stop = self.__exit__
                return playwright
            _pw_cm.PlaywrightContextManager.__enter__ = _safe_enter
        except Exception:
            pass

        # Try launch with existing profile, retry with fresh profile on crash
        import tempfile
        for _attempt in range(2):
            try:
                context = launch_persistent_context(
                    user_data_dir=profile_dir,
                    geoip=True, proxy=browser_proxy, humanize=True, headless=headless,
                    viewport=config['viewport'],
                    human_preset="careful",
                    user_agent=clean_ua, # V5: Force clean UA
                    args=launch_args,
                    ignore_https_errors=True,
                )
                break  # Success
            except Exception as e:
                if _attempt == 0 and ("Target page, context or browser has been closed" in str(e)
                                       or "exit code" in str(e).lower()):
                    sp(f"  [!] Browser profile corrupted, retrying with fresh profile...")
                    profile_dir = tempfile.mkdtemp(prefix="fresh_profile_")
                    first_run_path = os.path.join(profile_dir, ".first_run_done")
                    continue
                raise
        # Mark first run done after successful launch
        try:
            with open(first_run_path, 'w') as f:
                f.write('1')
        except: pass
        page = context.new_page()
        browser = context # Keep reference for compatibility with finally block
        page.set_default_timeout(60000)
        
        # V5: FWCIM Warmup — move mouse naturally before any interaction
        time.sleep(2.0)
        try:
            page.mouse.move(random.randint(200, 600), random.randint(200, 400), steps=10)
            time.sleep(1.0)
            page.mouse.move(random.randint(400, 800), random.randint(100, 300), steps=15)
            sp("  [+] FWCIM Warmup complete (mouse movement)")
        except Exception as e:
            sp(f"  [!] FWCIM Warmup failed: {e}")

        # Phase 1: Account creation
        sp("\n  -- CREATE ACCOUNT --")
        name, email, pwd = create_account(page, domain, run_idx=config['preset_idx'], step_results=step_results, mail_provider=mail_provider)
        run_one._run_idx = getattr(run_one, '_run_idx', 0) + 1
        sp(f"\n  [+] Account created: {email}")

        # Save credential IMMEDIATELY after creation (independent of panel).
        try:
            save_creds(email, pwd, panel_url, name)
            sp(f"\n  ✅ Credential saved (pre-panel): {email}")
        except Exception as _se:
            sp(f"\n  [!] Pre-panel save failed: {_se}")

        # Brief pause before panel add
        gap_sec = random.randint(15, 30)
        sp(f"  [*] Brief pause ({gap_sec}s) before panel add...")
        time.sleep(gap_sec)

        # Phase 2: Panel — SAME browser, SAME proxy, SAME fingerprint
        sp("\n  -- PANEL LOGIN (same browser, same proxy) --")
        if panel_login(page, panel_url, panel_pass):
            sp("\n  -- ADD TO PANEL --")
            # Exchange auth_code for tokens (for panel import)
            if _exchange_auth_code_for_tokens():
                sp("  [+] Tokens captured for panel import")
            added = panel_add_account(page, email, pwd, panel_url, mail_provider=mail_provider, refresh_token=_captured_tokens.get("refresh_token", ""))
            # Fallback: try universal panel driver if default failed
            if not added and PANEL_DRIVERS_OK:
                sp("  [*] Retrying with universal panel driver...")
                try:
                    driver_cls = _get_panel_driver(panel_url, page)
                    if driver_cls and hasattr(driver_cls, '__name__') and 'Universal' in driver_cls.__name__:
                        driver = driver_cls(panel_url, panel_pass)
                        if driver.login(page):
                            added = driver.add_account(page, email, pwd, mail_provider=mail_provider)
                except Exception as _ude:
                    sp(f"  [!] Universal driver error: {_ude}")
            if added:
                save_creds(email, pwd, panel_url, name)
                sp("\n  ✅ Account created and linked!")
            else:
                save_creds(email, pwd, panel_url, f"{name} (panel-pending)")
                sp("\n  ⚠️ Account created but panel add may have failed")
        else:
            sp("\n  [!] Panel login failed")
            save_creds(email, pwd, panel_url, f"{name} (panel-login-fail)")

        # Phase 2b: Add to extra panels (same browser session)
        if extra_panels:
            for ep_url, ep_pass in extra_panels:
                sp(f"\n  -- ADD TO EXTRA PANEL: {ep_url} --")
                try:
                    if panel_login(page, ep_url, ep_pass):
                        added_ep = panel_add_account(page, email, pwd, ep_url, mail_provider=mail_provider, refresh_token=_captured_tokens.get("refresh_token", ""))
                        if added_ep:
                            save_creds(email, pwd, ep_url, name)
                            sp(f"  ✅ Linked to {ep_url}")
                        else:
                            save_creds(email, pwd, ep_url, f"{name} (panel-pending)")
                            sp(f"  ⚠️ Panel add may have failed for {ep_url}")
                    else:
                        save_creds(email, pwd, ep_url, f"{name} (panel-login-fail)")
                        sp(f"  [!] Panel login failed for {ep_url}")
                except Exception as epe:
                    sp(f"  [!] Extra panel error ({ep_url}): {epe}")

        success = email is not None

    except Exception as e:
        sp(f"\n  [!] Exception: {e}")
        import traceback; traceback.print_exc()
        for s in STEPS:
            if not step_results.get(s):
                ban_step = s
                break
        if not ban_step:
            ban_step = "unknown"

    finally:
        try: browser.close()
        except: pass
        # V6: Keep profile_dir for cookie/history persistence across runs
        # try: shutil.rmtree(profile_dir, ignore_errors=True) if profile_dir else None

    duration = time.time() - start_time
    result_text = "survived" if success else ("banned" if ban_step else "error")

    config_with_domain = dict(config)
    config_with_domain['domain'] = domain
    config_hash = db.upsert_config(config_with_domain)
    error_detail = str(e) if 'e' in dir() and not success else None
    db.record_attempt(config_hash, proxy_ip, proxy_org, config_with_domain,
                       result_text, ban_step, error_detail, duration)

    print_result_summary(config_with_domain, proxy_ip, proxy_org, ban_step, duration, success, db)

    return success, ban_step, config_hash, name, email

# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Kiro Builder ID — Self-Improving Anti-Ban Account Creator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_bot.py                          # Interactive mode (prompts for all)
  python run_bot.py -p URL -d domain -c us   # Quick run with args
  python run_bot.py --count 10               # Create 10 accounts
  python run_bot.py --count 4 --headless     # 4 accounts, headless mode
  python run_bot.py --count 0                # Unlimited (respecting daily limit)
  python run_bot.py --daily-limit 500        # Max 500/day (default)
  python run_bot.py --min-gap 120 --max-gap 480  # Anti-ban gap 2-8 min
""",
    )
    ap.add_argument("--panel","-p", help="9Router panel URL (single panel mode)")
    ap.add_argument("--password","-w", default="", help="Panel password (single panel mode)")
    ap.add_argument("--panels", help="Path to panels.json for multi-panel mode (same account added to all)")
    ap.add_argument("--interval","-i", default="3m")
    ap.add_argument("--domain","-d", default="",
                    help="Comma-separated catch-all domains to rotate")
    ap.add_argument("--country","-c", default="",
                    help="Comma-separated countries: us, no, se, etc")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--visible", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--count", type=int, default=0,
                    help="Number of accounts to create (0 = unlimited)")
    ap.add_argument("--no-proxy", action="store_true", help="Skip proxy — use direct connection (e.g., Opera VPN)")
    ap.add_argument("--vpn-toggle", action="store_true", help="Prompt to toggle VPN for new IP before each account")
    ap.add_argument("--opera", action="store_true", help="Opera VPN mode — cycle Opera VPN + no-proxy browser for residential IP")
    ap.add_argument("--manual-otp", help="6-digit OTP code to inject instead of IMAP polling")
    ap.add_argument("--stats", action="store_true", help="Show learning DB stats and exit")
    ap.add_argument("--max-retries-per-acc", type=int, default=50, help="Max retries for one account before giving up")
    ap.add_argument("--verify-panel", action="store_true", help="Verify account in panel after adding")
    ap.add_argument("--daily-limit", type=int, default=500,
                    help="Max accounts per day (0 = unlimited, default=500)")
    ap.add_argument("--min-gap", type=int, default=120,
                    help="Minimum seconds between accounts for anti-ban (default=120)")
    ap.add_argument("--max-gap", type=int, default=480,
                    help="Maximum seconds between accounts for anti-ban (default=480)")
    ap.add_argument("--mail-provider", default="",
                    help="Mail provider: gsuite_imap (default), shiromail, yydsmail, fake_legal")
    ap.add_argument("--fake-legal-domain", default="",
                    help="Domain for fake.legal provider: fake.legal, imgui.de, pulsewebmenu.de, gooncraft.de")
    # ── IMAP Configuration for havenhaus mail provider ──
    ap.add_argument("--imap-host", default="imap.gmail.com",
                    help="IMAP host for OTP retrieval (default: imap.gmail.com)")
    ap.add_argument("--imap-port", type=int, default=993,
                    help="IMAP port (default: 993)")
    ap.add_argument("--imap-user", default="",
                    help="IMAP username for OTP retrieval")
    ap.add_argument("--imap-pass", default="",
                    help="IMAP password/app-password for OTP retrieval")
    ap.add_argument("--panel-password", default="",
                    help="Panel password (alias for --password)")
    # ── Self-heal ──
    ap.add_argument("--self-heal", action="store_true",
                    help="Enable self-healing mode: auto-restart on crash")
    ap.add_argument("--callback-port", type=int, default=3128,
                    help="Callback server port")
    ap.add_argument("--restart-delay", type=int, default=30,
                    help="Self-heal restart delay in seconds (default=30)")
    ap.add_argument("--batch-report", default="",
                    help="Export batch report to JSON/CSV file after run")
    args = ap.parse_args()

    sp("=" * 60)
    sp("  Kiro Builder ID — Self-Improving Anti-Ban Bot")
    sp("  SQLite learning DB · Config rotation · Auto-recovery")
    sp("=" * 60)

    if not CAMOUFOX_OK:
        sp("ERROR: Camoufox not installed. Run: pip install camoufox[geoip]")
        return 1

    db = LearningDB()

    if args.stats:
        stats = db.get_stats()
        sp(f"\n  📊 Learning DB Stats:")
        sp(f"     Total attempts:  {stats['total']}")
        sp(f"     Survived:        {stats['survived']}")
        sp(f"     Banned:          {stats['banned']}")
        sp(f"     Errors:          {stats['errors']}")
        sp(f"     Active configs:  {stats['active_configs']}/{stats['total_configs']}")
        survival_rate = (stats['survived'] / stats['total'] * 100) if stats['total'] else 0
        sp(f"     Survival rate:   {survival_rate:.1f}%")
        return 0

    using_proxy = not (args.no_proxy or args.opera)
    if args.opera:
        sp("  [i] Opera VPN mode — will cycle Opera VPN for residential IP, no proxy")
    elif args.no_proxy:
        sp("  [i] No-proxy mode — using direct connection (ensure VPN/Opera VPN is active)")
    else:
        sp("  [i] Using ProxyScrape free proxy API (residential rotation by country)")

    # ═══════════════════════════════════════════════════════════════
    # Interactive CLI — prompt for missing values
    # ═══════════════════════════════════════════════════════════════
    sp("\n  ╔══════════════════════════════════════════════════════════════╗")
    sp("  ║       Kiro Builder ID — Account Creator CLI                ║")
    sp("  ╚══════════════════════════════════════════════════════════════╝")

    # Multi-panel mode: load panels.json
    panels_list = []  # [(url, pass), ...]
    if args.panels:
        try:
            with open(args.panels) as f:
                _panels_raw = json.load(f)
            for _p in _panels_raw:
                panels_list.append((_p["url"], _p["pass"]))
            sp(f"  [+] Loaded {len(panels_list)} panel(s) from {args.panels}")
        except Exception as e:
            sp(f"  [!] Failed to load panels.json: {e}")
            return 1

    # Single panel mode (fallback)
    if not panels_list:
        panel_url = args.panel or input("  ▸ Panel URL (e.g. https://rd63vjg.abc-tunnel.us): ").strip()
        if not panel_url:
            sp("  [!] Panel URL is required. Use -p or enter manually.")
            return 1
        panel_pass = args.password or input("  ▸ Panel Password (leave empty if none): ").strip()
        panels_list = [(panel_url, panel_pass)]

    # For backward compat: primary panel is the first one
    panel_url, panel_pass = panels_list[0]

    # Domain — support fake.legal disposable domains
    if not args.domain:
        domains_input = input("  ▸ Domain (e.g. havenhaus.in, or fake.legal for disposable): ").strip()
        domains = [d.strip() for d in domains_input.split(",") if d.strip()]
    else:
        domains = [d.strip() for d in args.domain.split(",") if d.strip()]
    if not domains:
        domains = ["havenhaus.in"]

    # V8: If --mail-provider fake_legal, add fake.legal domains to the pool
    if args.mail_provider == "fake_legal":
        fl_domain = args.fake_legal_domain or "fake.legal"
        if fl_domain not in domains:
            domains.append(fl_domain)
            sp(f"  [+] Added fake.legal domain: {fl_domain}")
        sp(f"  [i] Using fake.legal temp mail provider — inbox expires in 3 minutes!")

    # Country
    if not args.country:
        countries_input = input("  ▸ Country (e.g. us,no,se — comma separated): ").strip()
        countries = [c.strip() for c in countries_input.split(",") if c.strip()]
    else:
        countries = [c.strip() for c in args.country.split(",") if c.strip()]
    if not countries:
        countries = ["us"]

    # Count
    if args.count <= 0 and not args.once:
        count_input = input("  ▸ How many accounts? (enter number): ").strip()
        try:
            target_count = int(count_input)
        except (ValueError, TypeError):
            target_count = 1
    elif args.once:
        target_count = 1
    else:
        target_count = args.count

    # Headless
    headless = args.headless if args.headless else (not args.visible)

    # Show summary
    sp(f"\n  📋 Configuration:")
    sp(f"     Panel URL:   {panel_url}")
    sp(f"     Panel Pass:  {'(set)' if panel_pass else '(none)'}")
    sp(f"     Domain(s):   {', '.join(domains)}")
    sp(f"     Country(s):  {', '.join(countries)}")
    sp(f"     Accounts:    {target_count}")
    sp(f"     Headless:    {headless}")
    sp(f"     Max Retries: {args.max_retries_per_acc}")

    # ═══════════════════════════════════════════════════════════════
    # Multi-Account Loop
    # ═══════════════════════════════════════════════════════════════
    sp("\n  ╔══════════════════════════════════════════════════════════════╗")
    sp("  ║      STARTING ACCOUNT CREATION                              ║")
    sp("  ╚══════════════════════════════════════════════════════════════╝")

    total_success = 0
    total_failed = 0
    created_emails = []
    start_time = time.time()

    # ═══════════════════════════════════════════════════════════════
    # Daily Limit Tracking
    # ═══════════════════════════════════════════════════════════════
    _daily_file = BASE_DIR / ".daily_counter.json"
    def _load_daily():
        try:
            data = json.loads(_daily_file.read_text())
            today = datetime.now().strftime("%Y-%m-%d")
            if data.get("date") != today:
                return {"date": today, "success": 0, "failed": 0, "total": 0}
            return data
        except Exception:
            return {"date": datetime.now().strftime("%Y-%m-%d"), "success": 0, "failed": 0, "total": 0}
    def _save_daily(data):
        _daily_file.write_text(json.dumps(data, indent=2))
    _daily = _load_daily()
    daily_limit = args.daily_limit  # 0 = unlimited

    if daily_limit > 0 and _daily["success"] >= daily_limit:
        sp(f"\n  [!] Daily limit reached ({daily_limit}/{daily_limit}). Resuming tomorrow.")
        sp(f"  [*] Use --daily-limit 0 for unlimited.")
        return 0

    # ═══════════════════════════════════════════════════════════════
    # Unlimited mode: if --count 0 or --count > daily_limit, cap to remaining
    # ═══════════════════════════════════════════════════════════════
    if target_count <= 0:
        if daily_limit > 0:
            remaining = daily_limit - _daily["success"]
            target_count = max(1, remaining)
            sp(f"  [i] Unlimited mode — will create up to {target_count} accounts (daily limit: {daily_limit})")
        else:
            target_count = 999999  # truly unlimited
            sp(f"  [i] Unlimited mode — no daily limit")

    # Adjust if daily limit would be hit
    if daily_limit > 0:
        remaining = daily_limit - _daily["success"]
        if target_count > remaining:
            sp(f"  [i] Adjusting target from {target_count} to {remaining} (daily limit: {daily_limit}, already made: {_daily['success']})")
            target_count = remaining

    # ═══════════════════════════════════════════════════════════════
    # V8: Instantiate mail provider if specified
    # ═══════════════════════════════════════════════════════════════
    active_provider = None
    if args.mail_provider and MAIL_PROVIDERS_OK:
        try:
            provider_name = args.mail_provider.lower()
            provider_kwargs = {}
            if args.fake_legal_domain and provider_name != 'havenhaus':
                provider_kwargs['domain'] = args.fake_legal_domain
            elif args.fake_legal_domain and provider_name == 'havenhaus':
                provider_kwargs['domains'] = [args.fake_legal_domain]
            # Pass IMAP credentials for havenhaus/gsuite_imap providers
            if provider_name in ('havenhaus', 'gsuite_imap'):
                provider_kwargs['imap_host'] = args.imap_host or 'imap.gmail.com'
                provider_kwargs['imap_port'] = args.imap_port or 993
                provider_kwargs['imap_user'] = args.imap_user or ''
                provider_kwargs['imap_pass'] = args.imap_pass or ''
                if domains:
                    provider_kwargs['domains'] = domains
            # Use panel-password as alias for password
            if not panel_pass and args.panel_password:
                panel_pass = args.panel_password
            active_provider = get_provider(provider_name, **provider_kwargs)
            sp(f"  [+] Mail provider initialized: {active_provider.display_name}")
        except Exception as e:
            sp(f"  [!] Failed to init mail provider '{args.mail_provider}': {e}")
            active_provider = None

    for acc_num in range(1, target_count + 1):
        # ═══════════════════════════════════════════════════════════════
        # Anti-Ban Gap Delay (between accounts, not before first)
        # ═══════════════════════════════════════════════════════════════
        if acc_num > 1:
            gap = random.randint(args.min_gap, args.max_gap)
            sp(f"\n  🛡️ Anti-ban gap: waiting {gap}s ({gap//60}m {gap%60}s) before next account...")
            sp(f"  [*] Random delay prevents instant-ban detection by AWS")
            for r in range(gap, 0, -5):
                try:
                    sys.stdout.write(f"\r  Next account in {r}s...   ")
                    sys.stdout.flush()
                except: pass
                time.sleep(min(5, r))
            sp("")  # newline after countdown
        sp(f"\n{'═' * 60}")
        sp(f"  🎯 ACCOUNT {acc_num}/{target_count}")
        sp(f"{'═' * 60}")

        attempt = 0
        account_created = False
        acc_start = time.time()

        while not account_created:
            attempt += 1
            sp(f"\n  ── Attempt #{attempt} ──")

            # ── 1. Cycle Opera VPN (if --opera) or normal proxy setup ──
            if args.opera:
                opera_vpn_cycle()
                no_proxy_mode = True
                proxy_country = None
            elif args.no_proxy:
                no_proxy_mode = True
                proxy_country = None
            else:
                no_proxy_mode = False
                proxy_country = random.choice(countries)

            domain = random.choice(domains)

            # ── 2. Generate config (DB-aware) ──
            disabled_presets = db.get_disabled_presets()
            config = generate_config(db=db, disabled_presets=disabled_presets)
            sp(f"  Config: OS={config['os']} Preset=#{config['preset_idx']} Profile={config['profile_type']}")
            if disabled_presets:
                sp(f"  Disabled presets: {sorted(disabled_presets)}")

            # ── 3. Run one account creation ──
            success, ban_step, c_hash, name, email = run_one(
                panel_url, panel_pass, domain, proxy_country or 'us',
                headless, config, db, no_proxy=no_proxy_mode,
                mail_provider=active_provider,
                extra_panels=panels_list[1:] if len(panels_list) > 1 else None
            )

            # ── 4. SUCCESS → track and move to next account ──
            if success and email:
                total_success += 1
                _daily["success"] += 1
                _daily["total"] += 1
                _save_daily(_daily)
                created_emails.append(email)
                sp(f"\n  ✅ ACCOUNT {acc_num} CREATED — {email}")
                sp(f"  ⏱  Time: {time.time() - acc_start:.0f}s")
                sp(f"  📊 Daily: {_daily['success']}/{daily_limit}" if daily_limit > 0 else "")
                account_created = True
                break

            # ── 5. FAILURE → analyze, classify, recover ──
            sp(f"\n  ❌ Attempt #{attempt} failed (ban_step={ban_step})")

            # Capture diagnostics from the failed attempt
            try:
                if 'page' in dir() or 'page' in locals():
                    try:
                        if page:
                            diag = capture_diagnostics(page)
                    except:
                        diag = {'url':'','error_keywords':[],'body_snippet':ban_step or '','screenshot':None}
                else:
                    diag = {'url':'','error_keywords':[],'body_snippet':ban_step or '','screenshot':None}
            except:
                diag = {'url':'','error_keywords':[],'body_snippet':ban_step or '','screenshot':None}

            error_type, confidence, reason = classify_error(diag, ban_step)
            sp(f"  [analysis] Type={error_type} (confidence={confidence:.0%}) — {reason}")

            # ── 6. Targeted recovery ──
            config = targeted_recover(error_type, config, attempt)

            # ── 7. Mark in DB ──
            db.record_attempt("retry_"+str(attempt), "?", "?", {**config, 'domain':domain},
                              "retry", ban_step, f"{error_type}: {reason}", 0)

            # ── 8. Brief pause before retry (adaptive backoff) ──
            backoff = min(120, 15 + attempt * 5)
            sp(f"  [*] Retry pause: {backoff}s (attempt #{attempt})")
            for r in range(backoff, 0, -5):
                try:
                    sys.stdout.write(f"\r  Next retry in {r}s...   ")
                    sys.stdout.flush()
                except: pass
                time.sleep(min(5, r))

            # ── 9. Max check ──
            if attempt >= args.max_retries_per_acc:
                sp(f"\n  [!] Max retries ({args.max_retries_per_acc}) reached for account {acc_num}.")
                break

        if not account_created:
            total_failed += 1
            _daily["failed"] += 1
            _daily["total"] += 1
            _save_daily(_daily)
            sp(f"\n  ⚠️ ACCOUNT {acc_num} FAILED after {attempt} attempts")

    # ═══════════════════════════════════════════════════════════════
    # Final Summary
    # ═══════════════════════════════════════════════════════════════
    elapsed = time.time() - start_time
    sp(f"\n{'═' * 60}")
    sp(f"  📊 FINAL RESULTS")
    sp(f"{'═' * 60}")
    sp(f"  Target:        {target_count}")
    sp(f"  Success:       {total_success}")
    sp(f"  Failed:        {total_failed}")
    sp(f"  Success Rate:  {total_success/max(1,target_count)*100:.0f}%")
    sp(f"  Total Time:    {elapsed/60:.1f} min")
    if daily_limit > 0:
        sp(f"  Daily Used:    {_daily['success']}/{daily_limit}")
        sp(f"  Daily Failed:  {_daily['failed']}")
        sp(f"  Daily Total:   {_daily['total']}")
    sp(f"  Anti-Ban Gap:  {args.min_gap}-{args.max_gap}s between accounts")
    if created_emails:
        sp(f"\n  Created Emails:")
        for i, em in enumerate(created_emails, 1):
            sp(f"    {i}. {em}")
    sp(f"{'═' * 60}")
    if total_failed > 0:
        sp(f"\n  [!] {total_failed} account(s) failed. Check logs for details.")
    return 0 if total_failed == 0 else 1

# ══════════════════════════════════════════════════════════════════════════════
# SELF-HEAL WRAPPER — restarts main() on crash
# ══════════════════════════════════════════════════════════════════════════════
def self_heal_main():
    """Wrapper that restarts main() on crash with exponential backoff."""
    max_restarts = 10
    for restart_num in range(1, max_restarts + 1):
        sp(f"\n{'═' * 60}")
        sp(f"  🛡️ SELF-HEAL: Attempt #{restart_num}/{max_restarts}")
        sp(f"{'═' * 60}")
        try:
            result = main()
            if result == 0:
                sp("  [✓] Bot completed successfully.")
                return 0
            else:
                sp(f"  [!] Bot exited with code {result}")
                # Check if self-heal is enabled
                try:
                    _idx = sys.argv.index('--self-heal') if '--self-heal' in sys.argv else -1
                    if _idx == -1:
                        sp("  [*] Self-heal not enabled. Exiting.")
                        return result
                except (ValueError, IndexError):
                    sp("  [*] Self-heal not enabled. Exiting.")
                    return result
        except KeyboardInterrupt:
            sp("\n  Stopped by user.")
            return 0
        except Exception as e:
            sp(f"  [!] Crash detected: {e}")
        
        if restart_num < max_restarts:
            delay = min(300, 30 * restart_num)  # 30s, 60s, 90s... max 5min
            sp(f"  [*] Restarting in {delay}s...")
            time.sleep(delay)
        else:
            sp("  [!] Max restarts reached. Giving up.")
    return 1

if __name__ == "__main__":
    try:
        # Check if self-heal mode is requested
        if '--self-heal' in sys.argv:
            sys.exit(self_heal_main())
        else:
            sys.exit(main())
    except KeyboardInterrupt:
        sp("\n  Stopped by user.")
        sys.exit(0)
