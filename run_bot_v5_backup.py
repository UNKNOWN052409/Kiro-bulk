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
CSV_FILE = BASE_DIR / 'kiro_accounts.csv'
DB_FILE = BASE_DIR / 'learning.db'
SCREENSHOT_DIR = BASE_DIR / 'screenshots'
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
    """Generate email with varied patterns to avoid pattern detection."""
    parts = name.lower().split()
    first, last = parts[0], parts[-1] if len(parts) > 1 else 'user'
    domain = domain.lstrip('@')

    patterns = [
        lambda: f"{first}{last}{''.join(random.choices(string.digits, k=2))}@{domain}",
        lambda: f"{first}.{last}{''.join(random.choices(string.digits, k=2))}@{domain}",
        lambda: f"{first[0]}.{last}{''.join(random.choices(string.digits, k=2))}@{domain}",
        lambda: f"{first}{''.join(random.choices(string.digits, k=2))}@{domain}",
        lambda: f"{first}-{last}{''.join(random.choices(string.digits, k=2))}@{domain}",
        lambda: f"{first}_{last}{''.join(random.choices(string.digits, k=2))}@{domain}",
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
        page.wait_for_timeout(1000)
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
    """Get proxy candidate — uses the onrender working-proxy pool (onrender_pool.json).
    Falls back to Proxyrise residential if the pool file is absent."""
    import json as _json
    pool_path = BASE_DIR / 'onrender_pool.json'
    try:
        _pool = _json.load(open(pool_path))
        if _pool:
            c = random.choice(_pool)
            return {
                'server': c['server'],
                'username': c['username'],
                'password': c['password'],
            }
    except Exception:
        pass
    cfg = PROXY_PROVIDERS.get('residential')
    if not cfg:
        return None

    use_country = 'any'
    if random.random() < 0.30:
        use_country = random.choice(['us', 'gb', 'de', 'ca', 'au', 'fr', 'nl', 'se', 'no', 'dk'])

    username = cfg['format'].format(country=use_country)
    return {
        'server': cfg['server'],
        'username': username,
        'password': cfg['key'],
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
    'cloudflare': {'kw': ['cloudflare', 'checking your browser', 'just a moment', 'ddos protection'], 'desc': 'Cloudflare challenge → rotate OS+proxy country'},
    'aws_waf':   {'kw': ["enable javascript", "it's not you", 'something went wrong', 'try again later'], 'desc': 'AWS WAF/JS block → viewport+slow profile'},
    'datacenter':{'kw': ['datacenter'], 'desc': 'Datacenter IP → switch proxy country'},
    'proxy_ko':  {'kw': ['timeout', 'err_connection_timeout', 'err_proxy_connection'], 'desc': 'Proxy timeout → switch country'},
    'rate':      {'kw': ['rate limit', 'too many requests', '429'], 'desc': 'Rate limited → slow profile'},
    '403':       {'kw': ['403', 'forbidden', 'access denied'], 'desc': '403 block → full rotation'},
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
    for et, info in ERROR_PATTERNS.items():
        if any(k in kwl for k in info['kw']):
            return et, 0.7, info['desc']
    if ban_step and '403' in str(ban_step):
        return '403', 0.6, '403 detected in step'
    if ban_step:
        return 'step_fail', 0.5, f'Failed at step: {ban_step}'
    return 'unknown', 0.3, 'No clear error pattern'

def targeted_recover(error_type, config, attempt_num):
    config = dict(config)
    if error_type == 'cloudflare':
        config['os'] = random.choice(['macos','linux'])
        config['profile_type'] = 'slow' if attempt_num>2 else 'variable'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(4,7))%12
        sp(f"  [recovery] Cloudflare: OS→{config['os']}, preset→#{config['preset_idx']}")
    elif error_type == 'aws_waf':
        config['viewport'] = random.choice(VIEWPORTS['macos']+VIEWPORTS['linux'])
        config['profile_type'] = 'slow'
        config['preset_idx'] = (config.get('preset_idx',0)+random.randint(3,6))%12
        sp(f"  [recovery] AWS WAF: slow+preset→#{config['preset_idx']}")
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
        page.wait_for_timeout(5000)
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
        page.wait_for_timeout(delay)

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
        page.keyboard.type(text)
    except Exception:
        # Fallback: raw character-by-character typing
        for i in range(len(text)):
            delay = random.randint(delay_range[0], delay_range[1])
            page.keyboard.type(text[i], delay=delay)
    page.wait_for_timeout(random.randint(200, 500))

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
        page.wait_for_timeout(random.randint(200, 500))
    except Exception:
        pass

def human_idle(page, min_sec=1, max_sec=3):
    """Brief idle pause."""
    try:
        page.wait_for_timeout(int(random.uniform(min_sec * 1000, max_sec * 1000)))
    except Exception:
        pass

def human_wait_page_load(page):
    """Wait briefly for page to load with human-like behavior."""
    page.wait_for_timeout(int(random.uniform(800, 2000)))
    try:
        page.mouse.wheel(0, random.randint(50, 150))
        page.wait_for_timeout(random.randint(300, 800))
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

def organic_navigate_to_kiro(page, run_idx):
    """Navigate to Kiro signin with PKCE params (OIDC registration + callback server)."""
    sp(f"  [*] Navigation: preset #{run_idx % len(NAV_PRESETS)} — PKCE signin")

    # Ensure callback server and OIDC client are ready
    _start_callback_server()
    if not _register_oidc_client():
        sp("  [!] OIDC registration failed, falling back to direct signin")
        page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(random.randint(1000, 2000))
        return

    # Navigate to Kiro signin with PKCE params
    page.goto(_oidc_client["signin_url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(random.randint(1000, 2000))

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
    # Hash-based routes on profile.aws.amazon.com
    if "profile.aws" in url:
        if "verify-otp" in hash_fragment or "verifyotp" in hash_fragment:
            return "verify-otp"
        if "password" in hash_fragment or "set-password" in hash_fragment or "create-password" in hash_fragment:
            return "password"
        # Distinguish enter-email (after failed name submit) from signup-start (name page)
        if "enter-email" in hash_fragment:
            # Check if ERR-837 is shown
            try:
                body = page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''").lower()
                if "err-837" in body or "error processing" in body:
                    return "error"
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
    if "signup" in url and "aws" in url and "password" not in url.lower(): return "signup-start"

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
            if (body.includes("it's not you") || body.includes('something went wrong'))
                return 'error';

            return null;
        }""")
        if state: return state
    except Exception:
        pass

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
        page.wait_for_timeout(2000)
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
        gmail_page.wait_for_timeout(int(random.uniform(5000, 8000)))

        body_text = gmail_page.locator("body").text_content() or ""
        bl = body_text.lower()

        if "sign in" in bl or "log in" in bl:
            sp("    [!] Gmail not logged in, trying alternative URL...")
            gmail_page.goto("https://gmail.com", wait_until="domcontentloaded", timeout=30000)
            gmail_page.wait_for_timeout(int(random.uniform(5000, 8000)))
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
                            gmail_page.wait_for_timeout(int(random.uniform(3000, 6000)))
                            break
                    except Exception:
                        pass

                email_body = gmail_page.locator("body").text_content() or ""
                code = extract_code(email_body)
                if code:
                    sp(f"    [+] OTP via visual Gmail: {code}")
                    return code

                human_scroll(gmail_page)
                gmail_page.wait_for_timeout(int(random.uniform(3000, 5000)))

            human_scroll(gmail_page, direction=-1)
            gmail_page.wait_for_timeout(int(random.uniform(3000, 6000)))

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

def create_account(page, domain, run_idx=0, step_results=None):
    """Create AWS Builder ID with ONLY Camoufox native interactions + step tracking."""
    if step_results is None:
        step_results = {}

    name = gen_name()
    email = gen_email(name, domain)
    password = gen_password()
    sp(f"  Name:     {name}")
    sp(f"  Email:    {email}")
    sp(f"  Password: {password}")

    step_results['navigate'] = True
    organic_navigate_to_kiro(page, run_idx)

    step_results['click_builder'] = True
    sp("  Clicking AWS Builder ID (JS dispatch)...")
    builder_clicked = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const target = btns.find(b => b.textContent.includes('Builder ID') && b.offsetWidth > 0);
        if (!target) return false;
        target.scrollIntoView({block: 'center', behavior: 'instant'});
        target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        return true;
    }""")
    if not builder_clicked:
        raise Exception("Could not find AWS Builder ID button")
    sp("  [+] AWS Builder ID clicked (JS)")

    # After clicking Builder ID, Kiro SPA sends a callback to our local server.
    # Wait for the callback, then navigate to OIDC authorize URL.
    sp("  [*] Waiting for Kiro callback...")
    for _ in range(15):
        page.wait_for_timeout(2000)
        if _callback_server["signin_params"]:
            sp(f"  [+] Signin callback received: {dict(_callback_server['signin_params'])}")
            break
    
    if _callback_server["signin_params"]:
        # Navigate to OIDC authorize URL
        if _navigate_to_oidc_authorize(page):
            sp("  [+] Navigated to OIDC authorize page")
        else:
            sp("  [!] OIDC authorize navigation failed")
    else:
        sp("  [!] No callback received, waiting for direct AWS redirect...")

    # Wait for AWS page (either from OIDC authorize redirect or direct)
    for _ in range(30):
        page.wait_for_timeout(3000)
        try:
            has_aws = page.evaluate("""() => {
                for (const i of document.querySelectorAll('input[type="email"]')) { if (i.offsetWidth > 0) return 'email'; }
                const t = document.title;
                if (t && t.includes('Amazon Web Services')) return 'title';
                if ((document.body?.innerText||'').includes('Continue with Google')) return 'content';
                if (location.href.includes('signin.aws') || location.href.includes('amazonaws.com')) return 'url';
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
        sp(f"  Waiting for AWS page... ({page.url[:80]})")
    else:
        # If we have OIDC params but AWS page still not loaded, try direct authorize
        if _callback_server["signin_params"] and _oidc_client["client_id"]:
            sp("  [*] Retrying OIDC authorize navigation...")
            _navigate_to_oidc_authorize(page)
            for _ in range(15):
                page.wait_for_timeout(3000)
                try:
                    has_aws = page.evaluate("""() => {
                        for (const i of document.querySelectorAll('input[type="email"]')) { if (i.offsetWidth > 0) return 'email'; }
                        const t = document.title;
                        if (t && t.includes('Amazon Web Services')) return 'title';
                        if (location.href.includes('signin.aws') || location.href.includes('amazonaws.com')) return 'url';
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
    click_text(page, "Accept", timeout=5000)

    email_loc = None
    for _ in range(20):
        page.wait_for_timeout(1500)
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
            page.wait_for_timeout(random.randint(800, 1800))
            human_type(page, email)
            # FWCIM needs time to register typing behavior
            page.wait_for_timeout(random.randint(800, 2000))
        sp("  [+] Email filled")
        # Longer delay before submitting — FWCIM tracks timing between actions
        page.wait_for_timeout(int(random.uniform(2500, 5000)))
        # Robust Submit - Try multiple methods (data-testid first, then text, then JS, then Enter)
        submitted = False
        for method in ["testid", "text", "js", "fallback"]:
            if method == "testid":
                try:
                    btn = page.locator('[data-testid="test-primary-button"]').first
                    if btn.is_visible(timeout=3000):
                        # V5: Hover before clicking
                        btn.hover()
                        page.wait_for_timeout(random.randint(500, 1200))
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
                        page.wait_for_timeout(random.randint(500, 1000))
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
        
        page.wait_for_timeout(int(random.uniform(4000, 7000)))

    # Wait for redirect to profile.aws.amazon.com and SPA to fully render
    # FWCIM needs extra time between page transitions
    sp("  [*] Waiting for AWS profile page and SPA render...")
    for _ in range(25):
        page.wait_for_timeout(3000)
        try:
            # Check if we're on the AWS profile page
            is_aws = page.evaluate("""() => {
                const u = location.href;
                if (u.includes('profile.aws.amazon.com')) return 'aws_profile';
                if (u.includes('signup') && u.includes('aws')) return 'signup_page';
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
                    sp(f"  [*] AWS page loaded but SPA not rendered yet, waiting...")
            elif "signin.aws" in page.url:
                # Still on signin page - maybe need to click Continue again
                sp(f"  [*] Still on signin page, clicking Continue...")
                click_text(page, "Continue", timeout=2000)
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
                
                # If body is empty (SPA loading), wait for render
                if not diag_body or len(diag_body.strip()) == 0:
                    sp("  [*] SPA loading after OTP, waiting for content...")
                    for render_wait in range(30):
                        page.wait_for_timeout(2000)
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
                
                # Check if it's actually the password page
                if 'password' in diag_url.lower() or 'create password' in diag_body.lower() or 'create your password' in diag_body.lower():
                    sp("  [!] LOOP DETECTED but page is PASSWORD page! Setting force_state...")
                    step_results['force_password'] = True
                    continue
                else:
                    sp("  [!] LOOP DETECTED: Transitioned back to signup-start after OTP submission.")
                    sp("      This usually means the OTP was rejected or the session expired.")
                    raise Exception("AWS signup loop detected after OTP submission")

            step_results['fill_name'] = True
            page.wait_for_timeout(2000)
            
            # Check for cookie consent / blank page / session timeout and handle it
            try:
                body_text = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                if "enable JavaScript" in body_text.lower():
                    sp("  [!] JS not loaded -- reloading...")
                    page.goto(page.url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                    continue
                elif "session timed out" in body_text.lower() or "oh no" in body_text.lower():
                    sp("  [!] Session timed out! Restarting workflow from signin page...")
                    page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                    attempt = 0
                    continue
                elif "cookie" in body_text.lower() or "privacy" in body_text.lower() or len(body_text) < 50:
                    # Cookie consent page or blank page - accept cookies and wait
                    sp(f"  [*] Cookie/blank page detected ({len(body_text)} chars), accepting...")
                    click_text(page, "Accept", timeout=3000) or click_text(page, "Accepter", timeout=3000) or \
                        click_text(page, "Decline", timeout=3000) or click_text(page, "Customize", timeout=2000) or click_text(page, "Refuser", timeout=2000)
                    page.wait_for_timeout(3000)
                    # If still blank after cookie handling, wait for SPA render
                    new_body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                    if len(new_body) < 50:
                        sp("  [*] Still blank after cookie accept, waiting for SPA...")
                        for rw in range(15):
                            page.wait_for_timeout(2000)
                            new_body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
                            if len(new_body) > 50:
                                sp(f"  [+] SPA rendered ({len(new_body)} chars)")
                                break
            except Exception:
                pass
            
            # Now wait for name input to appear (up to 20 seconds)
            # Must handle blank SPA page, CCBA overlay, and cookie consent
            for w in range(20):
                try:
                    has_name_field = page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"])');
                        for (const inp of inputs) {
                            if (inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled) {
                                const ph = (inp.placeholder || '').toLowerCase();
                                const nm = (inp.name || '').toLowerCase();
                                const id = (inp.id || '').toLowerCase();
                                const ac = (inp.autocomplete || '').toLowerCase();
                                // Check for name-related fields
                                if (ph.includes('name') || nm.includes('name') || id.includes('name')) return true;
                                // Check for autocomplete attributes
                                if (ac.includes('given-name') || ac.includes('family-name') || ac.includes('name')) return true;
                                // Check for text type inputs (but not if they're cookie checkboxes)
                                if (inp.type === 'text' && !id.includes('awsccc') && !nm.includes('awsccc')) return true;
                            }
                        }
                        return false;
                    }""") or False
                    if has_name_field:
                        sp("  [+] Name input found")
                        break
                except Exception:
                    pass
                page.wait_for_timeout(1000)
            
            page.wait_for_timeout(random.randint(500, 1200))

            # Name fill — use CloakBrowser locator-based fill (humanized)
            name_filled = False
            
            # Strategy 1: locator.click() + locator.fill() for CloakBrowser humanize pipeline
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
            
            for sel in selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible(timeout=1500):
                        inp.click()
                        # V5: Variable typing rhythm delay
                        page.wait_for_timeout(random.randint(600, 1500))
                        inp.fill(name)
                        name_filled = True
                        sp(f"  [+] Name filled: {name} (locator: {sel})")
                        break
                except Exception:
                    pass
            
            # Strategy 2: JS fallback if locator methods fail
            if not name_filled:
                try:
                    name_filled = page.evaluate("""(name) => {
                        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="password"]):not([type="email"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"])');
                        for (const inp of inputs) {
                            if (inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled) {
                                // Skip if it has a value already (not empty)
                                if (inp.value && inp.value.trim()) continue;
                                // Skip awsccc cookie-related inputs
                                const id = (inp.id || '').toLowerCase();
                                const nm = (inp.name || '').toLowerCase();
                                if (id.includes('awsccc') || nm.includes('awsccc')) continue;
                                // Use native setter + proper InputEvent for reliable detection
                                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeSetter.call(inp, name);
                                inp.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: name}));
                                inp.dispatchEvent(new Event('change', {bubbles: true}));
                                inp.dispatchEvent(new Event('blur', {bubbles: true}));
                                return true;
                            }
                        }
                        return false;
                    }""", name)
                    if name_filled:
                        sp(f"  [+] Name filled: {name} (JS fallback)")
                except Exception as e:
                    sp(f"  [!] JS fallback error: {e}")
            
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
                # V5: Thinking pause + FWCIM warmup before submit
                wait_time = random.randint(6000, 10000)
                sp(f"  [*] FWCIM humanizing: thinking pause {wait_time}ms...")
                page.wait_for_timeout(wait_time)
                
                # V5: Natural mouse movement before submit
                try:
                    page.mouse.move(random.randint(200, 800), random.randint(200, 600), steps=15)
                    page.wait_for_timeout(random.randint(500, 1000))
                except Exception:
                    pass
                
                # Random small scrolls to look human
                human_scroll(page, direction=1, amount=random.randint(50, 150))
                page.wait_for_timeout(random.randint(500, 1500))
                human_scroll(page, direction=-1, amount=random.randint(50, 150))
                page.wait_for_timeout(random.randint(300, 800))

                # Click Continue button using CloakBrowser locator (humanized)
                for w in range(5):
                    submitted = False
                    try:
                        # Try data-testid first (most reliable)
                        testid_btn = page.locator('[data-testid="test-primary-button"]').first
                        if testid_btn.is_visible(timeout=2000):
                            # V5: Hover before clicking to signal human presence
                            testid_btn.hover()
                            page.wait_for_timeout(random.randint(800, 1500))
                            testid_btn.click(timeout=3000)
                            submitted = True
                            sp(f"  [+] Continue clicked (data-testid, humanized)")
                    except Exception:
                        pass
                    
                    if not submitted:
                        try:
                            # Try native locator click
                            continue_btn = page.locator('button').filter(has_text=re.compile(r'continue|next', re.I)).first
                            if continue_btn.is_visible(timeout=1000):
                                # V5: Hover before clicking
                                continue_btn.hover()
                                page.wait_for_timeout(random.randint(500, 1200))
                                continue_btn.click(timeout=3000)
                                submitted = True
                                sp(f"  [+] Continue clicked (locator, humanized)")
                        except Exception:
                            pass
                    
                    if not submitted:
                        # Fallback: JS click
                        try:
                            page.evaluate("""() => {
                                const btns = document.querySelectorAll('button');
                                for (const b of btns) {
                                    const t = (b.textContent || '').trim().toLowerCase();
                                    if (b.offsetWidth > 0 && !b.disabled && (t.includes('continue') || t.includes('next'))) {
                                        b.scrollIntoView({block:'center', behavior:'instant'});
                                        b.click();
                                        return true;
                                    }
                                } return false;
                            """)
                            submitted = True
                            sp(f"  [+] Continue clicked (JS fallback)")
                        except Exception:
                            pass
                    
                    if not submitted:
                        sp(f"  [!] Continue button not found (attempt {w+1})")
                    
                    page.wait_for_timeout(random.randint(3000, 5000))
                    try:
                        ns = detect_state(page)
                        if ns not in ("signup-start", "unknown", "enter-email"):
                            sp(f"  [+] Transitioned to {ns}")
                            break
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
                # FWCIM cooldown: longer wait to let anti-bot reset
                page.wait_for_timeout(int(random.uniform(8000, 15000)))
                
                # Natural mouse movement during cooldown
                try:
                    page.mouse.move(random.randint(100, 900), random.randint(100, 700))
                    page.wait_for_timeout(random.randint(500, 1500))
                except Exception:
                    pass
                
                # Close error alert if present
                click_text(page, "Close", timeout=3000)
                page.wait_for_timeout(random.randint(1000, 2000))
                
                # Try to find and fill name again using locator (humanized)
                try:
                    # Use locator-based fill for CloakBrowser humanize pipeline
                    name_filled = False
                    for sel in ['input[placeholder*="name" i]', 'input[id*="name" i]', 'input[name*="name" i]',
                                'input[autocomplete*="name"]', 'input[autocomplete="given-name"]']:
                        try:
                            inp = page.locator(sel).first
                            if inp.is_visible(timeout=2000):
                                inp.click()
                                page.wait_for_timeout(random.randint(500, 1000))
                                inp.fill(name)
                                name_filled = True
                                sp(f"  [+] Name refilled (locator: {sel})")
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
                        page.wait_for_timeout(int(random.uniform(6000, 12000)))
                        
                        # Natural mouse movement before submit
                        try:
                            page.mouse.move(random.randint(300, 700), random.randint(300, 500))
                            page.wait_for_timeout(random.randint(500, 1500))
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
                        page.wait_for_timeout(int(random.uniform(6000, 12000)))
                except Exception as e:
                    sp(f"  [!] Retry error: {e}")
            else:
                sp("  [*] Error before name fill, restarting...")
                page.wait_for_timeout(10000)
            continue

        elif state == "enter-email":
            # Page went back to enter-email view (hash: #/signup/enter-email)
            sp("  [*] Page is on enter-email view, waiting for name page...")
            page.wait_for_timeout(int(random.uniform(5000, 10000)))
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
            else:
                # IMAP with retry (3 attempts with progressive backoff)
                for attempt in range(3):
                    timeout = 1800 if attempt == 0 else 120
                    code = poll_otp_imap(email, timeout=timeout)
                    if code:
                        break
                    if attempt < 2:
                        sp(f"  [*] IMAP attempt {attempt+1} failed, retrying in 10s...")
                        page.wait_for_timeout(10000)
            if not code:
                sp("  [*] IMAP exhausted, trying visual Gmail as fallback...")
                code = poll_otp_gmail_visual(page, timeout=120)
            if code:
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
                        page.wait_for_timeout(5000)
                    else:
                        for i, digit in enumerate(code):
                            if i < len(boxes):
                                b = boxes[i]
                                page.mouse.click(b['x'], b['y'], delay=random.randint(10, 30))
                                page.wait_for_timeout(random.randint(100, 300))
                                page.keyboard.type(digit, delay=random.randint(40, 100))
                                page.wait_for_timeout(random.randint(80, 200))
                        sp(f"  [+] OTP filled ({code})")
                        page.wait_for_timeout(random.randint(500, 1000))
                        page.keyboard.press('Tab')
                        page.wait_for_timeout(int(random.uniform(3000, 5000)))

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
                        page.wait_for_timeout(random.randint(200, 500))
                        human_type(page, code)
                        sp(f"  [+] OTP filled: {code}")
                        page.wait_for_timeout(int(random.uniform(1000, 2500)))
                        click_text(page, "Continue", timeout=5000) or \
                            click_text(page, "Verify", timeout=3000) or \
                            click_text(page, "Next", timeout=3000)
                        sp("  [+] OTP submitted")
                    else:
                        sp("  [!] OTP field not visible")
                        page.wait_for_timeout(5000)
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
                        page.wait_for_timeout(random.randint(200, 500))
                        human_type(page, code)
                        sp(f"  [+] OTP filled: {code}")
                        page.wait_for_timeout(int(random.uniform(1000, 2500)))
                        click_text(page, "Continue", timeout=5000) or \
                            click_text(page, "Verify", timeout=3000) or \
                            click_text(page, "Next", timeout=3000)
                        sp("  [+] OTP submitted")
                    else:
                        sp("  [!] No OTP input field found on page, waiting...")
                        page.wait_for_timeout(10000)

                sp("  [*] Waiting for OTP transition...")
                ns = wait_for_state_change(page, "verify-otp", timeout_sec=90)
                if ns: sp(f"  [+] Transitioned to {ns}")
                else: sp("  [!] Still on verify-otp after 90s")
            else:
                sp("  [!] No OTP received after all attempts")
                page.wait_for_timeout(10000)

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
                page.wait_for_timeout(random.randint(200, 500))
                human_type(page, password)
                sp("  [+] Password filled")
                pw_filled = True

                if pw_count >= 2:
                    try:
                        page.wait_for_timeout(int(random.uniform(1000, 2000)))
                        pw2 = page.locator('input[type="password"]').nth(1)
                        human_click(page, pw2)
                        page.wait_for_timeout(random.randint(200, 500))
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
                    page.wait_for_timeout(random.randint(200, 500))
                    human_type(page, password)
                    sp("  [+] Password filled via fallback")
                    pw_filled = True
                else:
                    sp("  [!] No password field found on page")
                    page.wait_for_timeout(5000)

            # Submit password form — always executed regardless of which branch filled it
            if pw_filled:
                page.wait_for_timeout(int(random.uniform(2000, 4000)))

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
                        page.wait_for_timeout(random.randint(500, 1000))
                except Exception:
                    pass

                step_results['create'] = True
                create = click_text(page, "Create AWS Builder ID", timeout=5000) or \
                         click_text(page, "Create", timeout=3000) or \
                         click_text(page, "Continue", timeout=3000)
                if create:
                    sp("  [+] Account created!")
                else:
                    sp("  [!] No Create/Continue button found after password")

                page.wait_for_timeout(int(random.uniform(2000, 4000)))

                step_results['redirect'] = True
                sp("  [*] Waiting for OAuth redirect and post-signup behavior...")
                for _ in range(30):
                    page.wait_for_timeout(2000)
                    if 'app.kiro.dev' in page.url:
                        sp("  [+] Redirected to Kiro app")
                        break

                step_results['explore'] = True
                post_start = time.time()
                post_duration = random.randint(30, 60)
                sp(f"  [*] Post-signup exploration: {post_duration}s...")
                while time.time() - post_start < post_duration:
                    human_scroll(page, random.choice([1, -1]))
                    page.wait_for_timeout(int(random.uniform(1500, 4000)))
                    for sel in ['button:has-text("New")', 'button:has-text("Create")',
                                'a:has-text("New Project")', 'button:has-text("Start")',
                                'a:has-text("Dashboard")', 'button:has-text("Settings")']:
                        try:
                            loc = page.locator(sel).first
                            if loc.is_visible(timeout=1000):
                                human_click(page, loc)
                                page.wait_for_timeout(int(random.uniform(2000, 4000)))
                                break
                        except Exception:
                            pass
                    try:
                        editor = page.locator('textarea, [contenteditable="true"], .cm-editor, .monaco-editor').first
                        if editor.is_visible(timeout=1000):
                            human_click(page, editor)
                            page.wait_for_timeout(int(random.uniform(500, 1500)))
                            human_type(page, random.choice([
                                'print("hello world")', 'const x = 42;', '// TODO: implement feature',
                                'def main():', 'import React from "react";',
                            ]), delay_range=(30, 120))
                            page.wait_for_timeout(int(random.uniform(1000, 3000)))
                    except Exception:
                        pass
                    for sel in ['nav a', 'button:has-text("Menu")', '[role="menuitem"]', 'header button']:
                        try:
                            loc = page.locator(sel).first
                            if loc.is_visible(timeout=1000):
                                human_click(page, loc)
                                page.wait_for_timeout(int(random.uniform(2000, 4000)))
                                break
                        except Exception:
                            pass
                    human_idle(page, 2, 5)

                return name, email, password

            page.wait_for_timeout(3000)

        elif state == "error":
            sp("  [!] Error page -- retrying...")
            take_screenshot(page, "error_page")
            page.wait_for_timeout(5000)
            try:
                page.goto("https://app.kiro.dev/signin", wait_until="domcontentloaded", timeout=30000)
                human_wait_page_load(page)
            except Exception:
                pass
            attempt = 0

        else:
            page.wait_for_timeout(4000)
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
    page.wait_for_timeout(2000)
    r = page.evaluate(f"""async () => {{
        try {{
            const r = await fetch('/api/auth/login', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{password:{json.dumps(panel_pass)}}})
            }});
            return {{ok: r.ok}};
        }} catch(e) {{ return {{ok:false, error:e.message}}; }}
    }}""")
    if r.get("ok"):
        sp("  [+] Panel logged in")
        page.goto(panel_url)
        page.wait_for_timeout(2000)
        return True
    sp(f"  [!] Panel login failed: {r}")
    return False

def panel_add_account(page, kiro_email, password, panel_url):
    """Add account to panel via device authorization flow.

    Uses the 9Router device auth flow: click Add → AWS Builder ID →
    open device URL → sign in with credentials → Allow → panel detects auth.
    """
    sp("  [*] Adding account to panel Kiro provider via device auth...")

    # Try multiple URL patterns for the dashboard
    dashboard_urls = [
        f"{panel_url}/dashboard/providers/kiro",        # /v1/dashboard/providers/kiro
        f"{panel_url.replace('/v1', '')}/v1/dashboard/providers/kiro",  # fallback
    ]
    
    # Actually, the dashboard might need to be accessed differently.
    # Let's first check what we get at the panel root after login
    page.goto(panel_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    panel_body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "")
    sp(f"  [*] Panel root body: {panel_body[:300]}")
    
    # Remove /v1 from URL to get base
    base_url = panel_url.replace('/v1', '').rstrip('/')
    
    # Try to find the right providers page
    providers_url = None
    for try_url in [
        f"{base_url}/dashboard/providers/kiro",
        f"{panel_url}/dashboard/providers/kiro",
        f"{base_url}/providers",
        f"{panel_url}/providers",
    ]:
        try:
            response = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('{try_url}', {{credentials: 'include'}});
                    const text = await r.text();
                    return {{ok: r.ok, status: r.status, text: text.substring(0, 300)}};
                }} catch(e) {{
                    return {{ok: false, error: e.message}};
                }}
            }}""")
            sp(f"  [*] Try {try_url}: status={response.get('status','?')} text={response.get('text','')[:100]}")
            if response.get('ok') and 'api key' not in (response.get('text','') or '').lower():
                providers_url = try_url
                break
        except Exception as e:
            sp(f"  [!] Error checking {try_url}: {e}")
    
    if providers_url:
        page.goto(providers_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        sp(f"  [+] Using providers URL: {providers_url}")
    else:
        sp("  [!] No working providers URL found. Trying direct navigation...")
        page.goto(f"{panel_url}/dashboard/providers/kiro", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

    # Wait for SPA to fully render
    for render_wait in range(20):
        body_len = len((page.evaluate("() => document.body?.innerText?.trim()||''") or ""))
        if body_len > 50:
            break
        page.wait_for_timeout(1000)
    sp(f"  [*] Page loaded ({body_len} chars)")

    # Click Add button using native Playwright click with multiple strategies
    add_clicked = False
    
    # Strategy 1: Native Playwright click - try multiple selectors
    add_selectors = [
        'button:has-text("Add")',
        'a:has-text("Add")',
        '[role="button"]:has-text("Add")',
        'button.add-provider',
        'button.btn-add',
        '[data-testid*="add"]',
    ]
    for sel in add_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                btn.click(timeout=5000)
                add_clicked = True
                sp(f"  [+] Clicked Add (native: {sel})")
                break
        except Exception:
            pass
    
    # Strategy 2: JS evaluate with NATIVE .click() (not dispatchEvent)
    if not add_clicked:
        add_clicked = page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, [role="button"], span, div');
            for (const el of all) {
                const t = (el.textContent || '').trim().toLowerCase().replace(/[\\s\\u00A0]+/g, '');
                if ((t === 'add' || t.includes('add')) && el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled) {
                    el.scrollIntoView({block:'center', behavior:'instant'});
                    el.click();
                    return true;
                }
            }
            return false;
        }""")
        if add_clicked:
            sp("  [+] Clicked Add (JS native .click())")
    
    page.wait_for_timeout(3000)
    
    # If still not clicked, try clicking any primary action button
    if not add_clicked:
        sp("  [!] Add button not found, trying any large clickable...")
        page.evaluate("""() => {
            const btns = document.querySelectorAll('button:not([disabled])');
            for (const b of btns) {
                if (b.offsetWidth > 50 && b.offsetHeight > 20) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(2000)

    # Click AWS Builder ID option in the dialog (using native clicks)
    aws_clicked = False
    
    # Strategy 1: Native Playwright click
    try:
        aws_btn = page.locator('button:has-text("AWS Builder ID")').first
        if aws_btn.is_visible(timeout=3000):
            aws_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            aws_btn.click(timeout=5000)
            aws_clicked = True
            sp("  [+] Clicked AWS Builder ID (native)")
    except Exception:
        pass
    
    # Strategy 2: JS native .click()
    if not aws_clicked:
        aws_clicked = page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, [role="button"], div, span');
            for (const el of all) {
                const t = (el.textContent || '').trim();
                if (t.replace(/[\\s\\u00A0]+/g, '').includes('AWSBuilderID') 
                    || t.includes('AWS Builder ID')
                    || t.includes('AWS IAM Identity Center')
                    || (t.includes('AWS') && t.includes('Builder'))) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled) {
                        el.scrollIntoView({block:'center', behavior:'instant'});
                        el.click();
                        return el.textContent.trim();
                    }
                }
            }
            return '';
        }""")
        if aws_clicked:
            sp(f"  [+] Clicked AWS Builder ID (JS: {aws_clicked[:50]})")
    
    page.wait_for_timeout(3000)

    # Wait for device code to load - try multiple dialog selectors
    sp("  [*] Waiting for device authorization code...")
    device_url = None
    user_code = None
    diag_text = ""

    for _ in range(30):
        page.wait_for_timeout(1000)
        
        # Try multiple dialog selectors
        diag_text = page.evaluate("""() => {
            // Try common modal/dialog selectors
            const sels = [
                '.fixed.inset-0', '[role="dialog"]', '.modal', '.dialog',
                '.fixed', '[class*="modal"]', '[class*="dialog"]',
                '.MuiModal-root', '[class*="overlay"]',
            ];
            for (const sel of sels) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                        const t = el.innerText || '';
                        if (t.length > 20) return t;
                    }
                }
            }
            // Fallback: get full page text
            return document.body?.innerText || '';
        }""")
        
        if not diag_text:
            continue
        
        # Try multiple URL patterns for device authorization
        url_patterns = [
            r'https://view\.awsapps\.com[^\s]*',
            r'https://device\.sso\.[^\s]*',
            r'https://[a-z0-9-]+\.awsapps\.com[^\s]*',
            r'https://[a-z0-9-]+\.sso\.[^\s]*',
            r'https://signin\.aws[^\s]*',
            r'https://[^\s]+\.amazonaws\.com[^\s]*',
        ]
        for pat in url_patterns:
            m = re.search(pat, diag_text)
            if m:
                device_url = m.group(0).rstrip(').')
                break
        
        if device_url:
            # Also try to get user code
            cm = re.search(r'(?:code|Code)[\s:]*\n?\s*([A-Z0-9-]{4,})', diag_text)
            if cm: user_code = cm.group(1)
            sp(f"  [+] Device URL: {device_url}")
            if user_code: sp(f"  [+] User Code: {user_code}")
            break
        
        # Print diagnostic info every 5 seconds
        if _ % 5 == 4:
            sp(f"  [*] Still waiting... diag_text({len(diag_text)} chars): {diag_text[:200]}")

    if not device_url:
        sp(f"  [!] Could not get device URL")
        sp(f"  [!] Page text: {diag_text[:400]}")
        take_screenshot(page, "panel_no_device_url")
        return False

    # Open device URL in a new tab (same context = same proxy, same fingerprint)
    sp("  [*] Opening device URL for sign-in (same browser context)...")
    auth_page = page.context.new_page()
    auth_page.set_default_timeout(30000)

    try:
        auth_page.goto(device_url, wait_until="domcontentloaded", timeout=30000)
        auth_page.wait_for_timeout(5000)
        
        # Take screenshot for debugging
        take_screenshot(auth_page, "device_auth_page")

        body_text = auth_page.evaluate("() => document.body ? document.body.innerText : ''")
        if "unable" in body_text.lower() and "error" in body_text.lower():
            sp(f"  [!] AWS error on device page: {body_text[:300]}")
            auth_page.close()
            return False

        # Check if already signed in (look for Allow button first)
        sp("  [*] Checking for existing session...")
        already_signed_in = False
        for _ in range(5):
            allow_found = auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if ((t.includes('allow') || t.includes('authorize')) && b.offsetWidth > 0) {
                        return b.textContent.trim();
                    }
                } return '';
            }""")
            if allow_found:
                sp(f"  [+] Already signed in, Allow button found: {allow_found}")
                already_signed_in = True
                break
            auth_page.wait_for_timeout(2000)
        
        if already_signed_in:
            # Click Allow
            try:
                allow_btn = auth_page.locator('button:has-text("Allow"), button:has-text("Authorize")').first
                if allow_btn.is_visible(timeout=3000):
                    allow_btn.click(timeout=5000)
                    sp("  [+] Allow clicked (native)")
            except Exception:
                auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').trim().toLowerCase();
                        if ((t.includes('allow') || t.includes('authorize')) && b.offsetWidth > 0 && !b.disabled) {
                            b.click();
                            return true;
                        }
                    } return false;
                }""")
                sp("  [+] Allow clicked (JS)")
            auth_page.wait_for_timeout(8000)
        else:
            # Not signed in, go through sign-in flow
            # Wait for email input
            sp("  [*] Waiting for sign-in form...")
            for step in range(15):
                if auth_page.evaluate('() => !!document.querySelector(\'input[type="email"]\')'):
                    break
                auth_page.wait_for_timeout(3000)
            
            # Fill email using native Playwright fill
            try:
                email_input = auth_page.locator('input[type="email"]').first
                email_input.wait_for(timeout=10000)
                email_input.click()
                auth_page.wait_for_timeout(300)
                email_input.fill(kiro_email)
                sp(f"  [+] Email filled (device): {kiro_email}")
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
                sp(f"  [+] Email filled (device JS): {kiro_email}")
            
            auth_page.wait_for_timeout(1500)

            # Submit email form - try clicking submit button, then Enter key
            email_submitted = False
            try:
                submit_btn = auth_page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Next"), button:has-text("Sign in")').first
                if submit_btn.is_visible(timeout=3000):
                    submit_btn.click(timeout=5000)
                    email_submitted = True
                    sp("  [+] Email submitted (native)")
            except Exception:
                pass
            
            if not email_submitted:
                email_submitted = auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.offsetWidth > 0 && !b.disabled) {
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t === '' || t.includes('sign') || t.includes('next') || t.includes('continue')) {
                                b.click(); return 'button:' + t;
                            }
                        }
                    }
                    return '';
                }""")
                if email_submitted:
                    sp(f"  [+] Email submitted (button: {email_submitted})")
                else:
                    auth_page.keyboard.press("Enter")
                    sp("  [+] Email submitted (Enter)")
            
            auth_page.wait_for_timeout(8000)
            
            # Take screenshot after email submit to see what happened
            take_screenshot(auth_page, "device_after_email")

            # Wait for password input
            for _ in range(20):
                if auth_page.evaluate('() => !!document.querySelector(\'input[type="password"]\')'):
                    break
                auth_page.wait_for_timeout(3000)

            # Fill password using native Playwright fill
            try:
                pw_input = auth_page.locator('input[type="password"]').first
                pw_input.wait_for(timeout=5000)
                pw_input.click()
                auth_page.wait_for_timeout(300)
                pw_input.fill(password)
                sp("  [+] Password filled (device, native)")
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
                sp("  [+] Password filled (device JS)")
            
            auth_page.wait_for_timeout(1500)
            
            # Take screenshot before sign-in
            take_screenshot(auth_page, "device_before_signin")

            # Submit password form - try multiple strategies
            pw_submitted = False
            
            # Strategy 1: Find and click submit button
            try:
                pw_submit = auth_page.locator('button[type="submit"]').first
                if pw_submit.is_visible(timeout=3000):
                    pw_submit.click(timeout=5000)
                    pw_submitted = True
                    sp("  [+] Password submitted (submit button)")
            except Exception:
                pass
            
            if not pw_submitted:
                # Strategy 2: Try clicking sign-in buttons
                pw_submitted = auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.offsetWidth > 0 && !b.disabled) {
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t.includes('sign') || t.includes('submit') || t.includes('login') || t === '' || t === 'sign in') {
                                b.click(); return 'button:' + t;
                            }
                        }
                    }
                    return '';
                }""")
                if pw_submitted:
                    sp(f"  [+] Password submitted ({pw_submitted})")
            
            if not pw_submitted:
                # Strategy 3: Try clicking any button that looks like sign-in
                pw_submitted = auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.offsetWidth > 0 && !b.disabled) {
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t.includes('sign') || t.includes('submit') || t.includes('login') || t === '' || t === 'sign in') {
                                b.click(); return 'button:' + t;
                            }
                        }
                    }
                    return '';
                }""")
                if pw_submitted:
                    sp(f"  [+] Password submitted ({pw_submitted})")
            
            if not pw_submitted:
                # Strategy 4: Click any visible button
                pw_submitted = auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled) {
                            b.click(); return 'any_button:' + (b.textContent || '').trim();
                        }
                    }
                    return '';
                }""")
                if pw_submitted:
                    sp(f"  [+] Password submitted ({pw_submitted})")
            
            if not pw_submitted:
                # Strategy 5: Enter key
                auth_page.keyboard.press("Enter")
                sp("  [+] Password submitted (Enter)")
            
            auth_page.wait_for_timeout(10000)
            
            # Take screenshot after sign-in to see what happened
            take_screenshot(auth_page, "device_after_signin")

        # Wait for Allow / Authorize button
        sp("  [*] Waiting for Allow/Authorize...")
        for _ in range(15):
            try:
                allow_btn = auth_page.locator('button:has-text("Allow"), button:has-text("Authorize")').first
                if allow_btn.is_visible(timeout=2000):
                    allow_btn.click(timeout=5000)
                    sp(f"  [+] Clicked: Allow (native)")
                    auth_page.wait_for_timeout(8000)
                    break
            except Exception:
                pass
            
            # Check page state
            page_text = auth_page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''")
            page_url = auth_page.url
            
            allow_text = auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if ((t.includes('allow') || t.includes('authorize')) && b.offsetWidth > 0 && !b.disabled) {
                        b.click();
                        return b.textContent.trim();
                    }
                } return '';
            }""")
            if allow_text:
                sp(f"  [+] Clicked: {allow_text} (JS)")
                auth_page.wait_for_timeout(8000)
                break
            
            if _ % 3 == 0:
                sp(f"  [diag] URL: {page_url[:100]}")
                sp(f"  [diag] Body: {page_text[:200]}")
            
            # Check for any post-login page (success, dashboard, etc.)
            if any(w in page_text.lower() for w in ['success', 'authorized', 'connected', 'code accepted', 'redirecting']):
                sp(f"  [+] Auth page detected: {page_text[:100]}")
                break
            
            auth_page.wait_for_timeout(2000)
        
        auth_page.wait_for_timeout(10000)

        # Click Allow / Authorize if present
        for _ in range(10):
            try:
                allow_btn = auth_page.locator('button:has-text("Allow"), button:has-text("Authorize")').first
                if allow_btn.is_visible(timeout=2000):
                    allow_btn.click(timeout=5000)
                    sp(f"  [+] Clicked: Allow (native)")
                    auth_page.wait_for_timeout(5000)
                    break
            except Exception:
                pass
            
            allow_text = auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if ((t.includes('allow') || t.includes('authorize')) && b.offsetWidth > 0 && !b.disabled) {
                        b.click();
                        return b.textContent.trim();
                    }
                } return '';
            }""")
            if allow_text:
                sp(f"  [+] Clicked: {allow_text} (JS)")
                auth_page.wait_for_timeout(5000)
                break
            auth_page.wait_for_timeout(2000)

        # Wait for panel to detect authorization
        sp("  [*] Waiting for panel to detect authorization...")
        auth_detected = False
        for _ in range(30):
            page.wait_for_timeout(2000)
            diag_after = page.evaluate("""() => {
                const sels = ['.fixed.inset-0', '[role="dialog"]', '.modal', '.dialog',
                              '.fixed', '[class*="modal"]', '[class*="dialog"]'];
                for (const sel of sels) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        if (el.offsetWidth > 0) return el.innerText.substring(0, 300);
                    }
                }
                return '';
            }""")
            if not diag_after:
                sp("  [+] Dialog closed — authorization detected!")
                auth_detected = True
                break
            if any(w in diag_after.lower() for w in ['success', 'connected', 'authorized']):
                sp(f"  [+] {diag_after[:200]}")
                auth_detected = True
                break

        auth_page.close()
        return auth_detected

    except Exception as e:
        sp(f"  [!] Device auth error: {e}")
        try: auth_page.close()
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

def run_one(panel_url, panel_pass, domain, proxy_country, headless, config, db, no_proxy=False):
    """Run one account creation cycle with config rotation and step tracking."""
    geo = COUNTRY_LOCALE.get(proxy_country, COUNTRY_LOCALE['us'])
    proxy_ip = None
    proxy_org = None
    profile_dir = None
    proxy = None
    browser = None

    if not no_proxy:
        # Phase 1 proxy — auto-retry on datacenter (HTTP check, no browser needed)
        import urllib.request, base64
        for retry in range(3):
            candidate = get_proxy_fallback(proxy_country)
            if not candidate or not candidate.get('server'):
                sp(f"  [!] No proxy candidate on attempt {retry+1}")
                continue
            sp(f"  Proxy attempt {retry+1}/3: {candidate.get('username','?')}")

            ok = False; info = None
            try:
                # HTTP proxy check via urllib — no browser context needed
                proxy_url = candidate['server']
                user_pass = f"{candidate['username']}:{candidate['password']}"
                encoded = base64.b64encode(user_pass.encode()).decode()
                req = urllib.request.Request("https://ipinfo.io/json")
                req.add_header("Proxy-Authorization", f"Basic {encoded}")
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({
                        'http': proxy_url, 'https': proxy_url
                    })
                )
                resp = opener.open(req, timeout=15)
                body = resp.read().decode()
                info = json.loads(body)
                org = (info.get("org") or "").lower()
                ip = info.get("ip", "?")
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
            sp("  [!] No valid proxy found after 3 retries!")
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

    profile_dir = tempfile.mkdtemp(prefix="camoufox_")

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
        
        context = launch_persistent_context(
            user_data_dir=profile_dir,
            geoip=True, proxy=browser_proxy, humanize=True, headless=headless,
            viewport=config['viewport'],
            human_preset="careful",
            user_agent=clean_ua, # V5: Force clean UA
            args=[
                "--fingerprint-noise=false",
                "--fingerprint-webrtc-ip=auto",
                "--disable-blink-features=AutomationControlled"
            ],
        )
        page = context.new_page()
        browser = context # Keep reference for compatibility with finally block
        page.set_default_timeout(60000)
        
        # V5: FWCIM Warmup — move mouse naturally before any interaction
        page.wait_for_timeout(2000)
        try:
            page.mouse.move(random.randint(200, 600), random.randint(200, 400), steps=10)
            page.wait_for_timeout(1000)
            page.mouse.move(random.randint(400, 800), random.randint(100, 300), steps=15)
            sp("  [+] FWCIM Warmup complete (mouse movement)")
        except Exception as e:
            sp(f"  [!] FWCIM Warmup failed: {e}")

        # Phase 1: Account creation
        sp("\n  -- CREATE ACCOUNT --")
        name, email, pwd = create_account(page, domain, run_idx=config['preset_idx'], step_results=step_results)
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
            added = panel_add_account(page, email, pwd, panel_url)
            if added:
                save_creds(email, pwd, panel_url, name)
                sp("\n  ✅ Account created and linked!")
            else:
                save_creds(email, pwd, panel_url, f"{name} (panel-pending)")
                sp("\n  ⚠️ Account created but panel add may have failed")
        else:
            sp("\n  [!] Panel login failed")
            save_creds(email, pwd, panel_url, f"{name} (panel-login-fail)")

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
        try: shutil.rmtree(profile_dir, ignore_errors=True) if profile_dir else None
        except: pass

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
    )
    ap.add_argument("--panel","-p", help="9Router panel URL")
    ap.add_argument("--password","-w", default="741085209630")
    ap.add_argument("--interval","-i", default="3m")
    ap.add_argument("--domain","-d", default="havenhaus.in",
                    help="Comma-separated catch-all domains to rotate")
    ap.add_argument("--country","-c", default="us")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--visible", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--no-proxy", action="store_true", help="Skip proxy — use direct connection (e.g., Opera VPN)")
    ap.add_argument("--vpn-toggle", action="store_true", help="Prompt to toggle VPN for new IP before each account")
    ap.add_argument("--opera", action="store_true", help="Opera VPN mode — cycle Opera VPN + no-proxy browser for residential IP")
    ap.add_argument("--manual-otp", help="6-digit OTP code to inject instead of IMAP polling")
    ap.add_argument("--stats", action="store_true", help="Show learning DB stats and exit")
    ap.add_argument("--max-retries-per-acc", type=int, default=50, help="Max retries for one account before giving up")
    ap.add_argument("--verify-panel", action="store_true", help="Verify account in panel after adding")
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
        import os as _os
        _pool_exists = _os.path.exists(BASE_DIR / 'onrender_pool.json')
        if not PROXY_PROVIDERS['residential']['server'] and not _pool_exists:
            sp("ERROR: PROXYRISE_SERVER env var not set and no onrender_pool.json! Usage: set PROXYRISE_SERVER=http://your-proxy:port")
            return 1
        if not PROXY_PROVIDERS['residential']['key'] and not _pool_exists:
            sp("ERROR: PROXYRISE_KEY env var not set and no onrender_pool.json!")

    panel_url = args.panel or input("  Panel URL: ").strip()
    panel_pass = args.password
    domains = [d.strip() for d in args.domain.split(",") if d.strip()]
    countries = [c.strip() for c in args.country.split(",") if c.strip()]
    headless = args.headless if args.headless else (not args.visible)

    sp("\n  ╔══════════════════════════════════════════════════════════════╗")
    sp("  ║      RESILIENT RETRY LOOP — WILL KEEP TRYING                ║")
    sp("  ║      Har error analysis + targeted recovery + fresh OTP     ║")
    sp("  ╚══════════════════════════════════════════════════════════════╝")

    attempt = 0
    account_created = False

    while not account_created:
        attempt += 1
        sp(f"\n{'=' * 60}")
        sp(f"  ACCOUNT ATTEMPT #{attempt}")
        sp(f"{'=' * 60}")

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
            headless, config, db, no_proxy=no_proxy_mode
        )

        # ── 4. SUCCESS → verify panel + done ──
        if success and email:
            sp(f"\n  ✅ ACCOUNT CREATED — {email}")

            # — 4a. Verify in panel if requested —
            if args.opera:
                sp("  [*] Opening panel to verify...")
                try:
                    with Camoufox(geoip=True, proxy=None, humanize=True, headless=headless, os=config.get('os','windows')) as v:
                        vp = v.new_page(); vp.set_default_timeout(60000)
                        from automation.automation.kiro_acc_creator import panel_login as old_login
                        page_got = vp
                        try:
                            panel_goto = panel_url
                            page_got.goto(panel_goto, wait_until="domcontentloaded")
                            page_got.wait_for_timeout(2000)
                            login_r = page_got.evaluate(f"""async () => {{
                                const r = await fetch('/api/auth/login', {{
                                    method:'POST', headers:{{'Content-Type':'application/json'}},
                                    body: JSON.stringify({{password:{json.dumps(panel_pass)}}})
                                }}); return {{ok: r.ok}};
                            }}""")
                            if login_r.get("ok"):
                                page_got.goto(panel_goto)
                                page_got.wait_for_timeout(2000)
                                verify_panel_account(page_got, panel_url, email)
                            else:
                                sp("  [*] Panel verify skipped: login failed")
                        except Exception as ev:
                            sp(f"  [*] Panel verify skipped: {ev}")
                except Exception as ev:
                    sp(f"  [*] Panel browser failed: {ev}")

            if args.verify_panel:
                sp("  [*] Verify-panel flag set, checking account...")
                try:
                    with Camoufox(geoip=True, proxy=None, humanize=True, headless=headless, os=config.get('os','windows')) as vv:
                        vvp = vv.new_page(); vvp.set_default_timeout(60000)
                        vvp.goto(panel_url, wait_until="domcontentloaded"); vvp.wait_for_timeout(2000)
                        rr = vvp.evaluate(f"""async () => {{
                            const r = await fetch('/api/auth/login', {{
                                method:'POST', headers:{{'Content-Type':'application/json'}},
                                body: JSON.stringify({{password:{json.dumps(panel_pass)}}})
                            }}); return {{ok: r.ok}};
                        }}""")
                        if rr.get("ok"):
                            vvp.goto(panel_url); vvp.wait_for_timeout(2000)
                            verify_panel_account(vvp, panel_url, email)
                except Exception as ev:
                    sp(f"  [*] Verify-panel browser error: {ev}")

            account_created = True
            sp(f"\n  🎉 ACCOUNT CREATED — exiting loop!")
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
        backoff = min(120, 15 + attempt * 5)  # 20s → 120s max
        sp(f"  [*] Retry pause: {backoff}s (attempt #{attempt})")
        for r in range(backoff, 0, -5):
            try:
                sys.stdout.write(f"\r  Next retry in {r}s...   ")
                sys.stdout.flush()
            except: pass
            time.sleep(min(5, r))

        # ── 9. Max check or --once flag ──
        if args.once:
            sp(f"\n  [!] --once flag set, exiting after first attempt.")
            break
        if attempt >= args.max_retries_per_acc:
            sp(f"\n  [!] Max retries ({args.max_retries_per_acc}) reached for this account.")
            sp("  [*] Add --max-retries-per-acc N to change.")
            break

    if account_created:
        sp("\n  ✅ ACCOUNT SUCCESSFULLY CREATED — all done!")
        return 0
    else:
        sp("\n  ⚠️ Failed to create account after all retries.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sp("\n  Stopped by user.")
        sys.exit(0)
