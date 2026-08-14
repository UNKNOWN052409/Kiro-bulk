# profile.aws.amazon.com Rendering Issue

## Problem
The Name page at `profile.aws.amazon.com` does NOT render (body is empty, HTML is only 1630 bytes). This happens both WITH and WITHOUT proxy. The SPA is not executing JavaScript properly.

## Key Findings
1. Without proxy: profile.aws.amazon.com shows empty body (1630 bytes HTML)
2. With proxy: Same issue - empty body
3. The SPA is NOT rendering in headless Chrome mode

## Root Cause
The `profile.aws.amazon.com` SPA requires a specific browser environment that headless Chrome doesn't provide. The page loads but JavaScript doesn't execute.

## Solution Options
1. Use non-headless mode with Xvfb (we already have DISPLAY=:99 set)
2. Add specific Chrome flags to make it behave more like a real browser
3. Use `--headless=new` instead of `--headless` (new headless mode is better)
4. Add `--disable-blink-features=AutomationControlled` flag

## What works
- The SSO portal (view.awsapps.com) renders fine in headless mode
- The signin.aws pages render fine in headless mode
- Only profile.aws.amazon.com fails to render

## ProxyRise Setup (WORKING)
- Relay: socks5_relay.py on 127.0.0.1:10800
- Forwards to gw.proxyrise.com:443 with auth username="api", password=API_KEY
- Chrome arg: `--proxy-server=socks5://127.0.0.1:10800`
- Each connection gets a different residential IP

## Current Script: final_production_v2.py
- Uses Playwright `launch` (not connect_over_cdp)
- Uses `--proxy-server=socks5://127.0.0.1:10800`
- Full flow: Email → Name → OTP → Password → Allow → Token
- The Name step navigates to profile.aws.amazon.com which doesn't render

## Next Steps
1. Fix profile.aws.amazon.com rendering (try non-headless or different flags)
2. Once fixed, test 1 account with proxy → should bypass ERR-837
3. Then test 2 concurrent
4. Then 10 concurrent
5. Then Rust container architecture
