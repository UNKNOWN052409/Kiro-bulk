# Current Status - CloakBrowser + ProxyRise

## What's Working
- CloakBrowser launches successfully (stealth: webdriver=false, plugins=5, chrome=object)
- Sign-in page loads fine through proxy
- Email submission works (redirects to profile.aws.amazon.com)
- Proxy works (US residential IP confirmed via curl)

## What's NOT Working
- profile.aws.amazon.com (Name page) NEVER renders through the proxy
  - Stuck at html_len=170 (essentially empty)
  - Even after 120+ seconds
  - This is the SAME issue as before with the SOCKS5 relay

## Key Finding
The profile.aws.amazon.com SPA is too heavy to load through ANY proxy (residential or relay).
It loads fine WITHOUT proxy (we tested this earlier).
It loads fine with proxy+bypass list for other domains (tested earlier).

## The Solution That Worked Before
When we used `proxy={'server': '...', 'bypass': '<-loopback>,*.amazonaws.com,*.awsapps.com,*.signin.aws,*.amazon.com'}` with regular Playwright (not CloakBrowser), the Name page DID load.

## Why It's Different with CloakBrowser
CloakBrowser's `proxy` parameter might not support the bypass list.
We need to pass the bypass through Chrome args instead.

## Next Steps
1. Try passing proxy bypass via Chrome args in CloakBrowser launch
2. Or use CloakBrowser without proxy for the Name page, then add proxy back
3. Or use a workaround: load the page without proxy, submit through proxy

## CloakBrowser Launch Options
From the README, CloakBrowser supports:
- `proxy="socks5://user:pass@host:port"` - native SOCKS5
- `geoip=True` - auto timezone/locale from proxy IP
- `humanize=True` - human-like interactions
- `headless=False` - non-headless mode

The issue is that CloakBrowser doesn't have a `bypass` parameter.
We need to find another way to bypass proxy for certain domains.
