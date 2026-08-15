# Status V26 - TES Block Analysis

## Confirmed: ERR-837 is REAL and persistent
The screenshot debug_tes_name.png shows: "ERR-837 - Sorry, there was an error processing your request. Please try again."

## Key Findings
1. **With residential proxy** → Goes to Kiro signup flow (us-east-1.signin.aws/platform/d-9067642ac7/login) → TES blocks on name submit
2. **Without proxy (VPS datacenter IP)** → Redirects to generic AWS console login (view.awsapps.com/start) → NOT the Kiro flow at all
3. **camoufox** → Incompatible with current Playwright version (isMobile parameter error)
4. **playwright-stealth** → Not sufficient to bypass TES
5. **undetected-chromedriver** → Installed but needs ChromeDriver binary matching Chromium 151

## TES Detection Mechanism
TES (Threat Evaluation Service) is blocking based on TLS/HTTP fingerprint of the automated browser, NOT the IP. The residential proxy gets us to the right page, but TES detects automation.

## What Still Needs Testing
- undetected-chromedriver with ChromeDriver 151 (patched Chrome binary)
- Longer delays between steps (maybe TES is timing-based)
- Using the browser's own cookies/session instead of fresh context
- Trying with a pre-existing browser profile with extensions

## Files
- kiro_hybrid.py: Browser + curl_cffi hybrid (currently browser has NO proxy for testing)
- kiro_creator.py: Original full browser approach
- proxy_wrapper_standalone.py: HTTP→SOCKS5 wrapper (port 8899) - keeps dying, needs restart
- socks5_bridge.py: SOCKS5→ProxyRise bridge (port 10800) - stable

## Working Components
- curl_cffi + HTTP proxy (8899) → OIDC registration ✓ (works)
- Gmail IMAP → OTP extraction ✓ (works)
- SOCKS5 bridge (10800) → ProxyRise residential proxy ✓ (works)

## Current Blocker
TES blocks the /api/execute calls from the automated browser on the Kiro signup page.
Need to find a browser solution that bypasses TES detection.
