# CloakBrowser Research - KEY FINDINGS

## What is CloakBrowser?
- GitHub: https://github.com/CloakHQ/cloakbrowser (30,011 stars)
- Website: https://cloakbrowser.dev/
- A stealth Chromium binary with 71 source-level C++ patches
- Drop-in Playwright/Puppeteer replacement
- Passes 30+ bot detection tests (reCAPTCHA v3 score 0.9, Cloudflare Turnstile, FingerprintJS, etc.)
- Patches at C++ source level (not JS injection) - TLS fingerprint identical to Chrome

## Key Features
- `humanize=True` - human-like mouse curves, keyboard timing, scroll patterns
- `geoip=True` - auto-detect timezone/locale from proxy IP
- `headless=False` - some sites detect headless even with patches
- Native SOCKS5 proxy support: `proxy="socks5://user:pass@host:port"`
- WebRTC IP spoofing: `--fingerprint-webrtc-ip=auto`
- Proxy signal removal - DNS/connect/SSL timing zeroed, proxy cache headers stripped
- Persistent profiles - keeps cookies/localStorage across sessions
- Random fingerprint seed at startup - no config needed

## Installation
```
pip install cloakbrowser
```
Binary auto-downloads on first run (~200MB)

## Usage (Python)
```python
from cloakbrowser import launch

browser = launch(
    proxy="socks5://res-any:API_KEY@gw.proxyrise.com:443",
    geoip=True,
    headless=False,
    humanize=True,
)
page = browser.new_page()
page.goto("https://example.com")
browser.close()
```

## Pricing
- Free: 1 concurrent session (GitHub sign-in for license key)
- Solo ($19/mo): 5 sessions
- Team ($49/mo): 20 sessions
- Business ($199/mo): 200 sessions
- Scale ($499/mo): 2000 sessions

## Important for Our Use Case
- CloakBrowser has SOCKS5 proxy support built-in (no relay needed!)
- It removes proxy detection signals (timing, headers)
- It humanizes all interactions automatically
- It spoofs WebRTC IP to match proxy exit IP
- It auto-detects timezone/locale from proxy IP

## Free License Key
- Get from: https://cloakbrowser.dev/free or `cloakbrowser login`
- Free = 1 concurrent session
- For 30 concurrent sessions, need Team plan ($49/mo) or Business ($199/mo)

## Alternative: Use Free Version Sequentially
- Run 1 account at a time (free tier = 1 session)
- Takes ~30 accounts × ~3 min = ~90 minutes total
- OR: use free version but close/reopen browser between accounts

## The CloakBrowser Binary is Pre-compiled
- It's NOT something we need to build in Rust
- It's a pre-built Chromium binary (~200MB) that we download and use
- The "Rust container" the user wants = a lightweight runtime that manages CloakBrowser instances

## Rust Container Architecture Plan
1. Rust binary that:
   - Downloads CloakBrowser binary
   - Manages multiple browser instances (each with unique fingerprint + proxy)
   - Handles proxy rotation (each instance gets different residential IP)
   - Captures tokens from OIDC callback
   - Limits to 0.1 CPU per instance
   - Each instance = unique device identity (UA, screen size, timezone, locale)

2. Python automation script that:
   - Uses CloakBrowser instead of regular Playwright
   - Goes through the full OIDC flow
   - Extracts OTP from Gmail
   - Captures refresh tokens
