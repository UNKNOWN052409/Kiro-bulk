# ProxyRise Residential Proxy Region Results

| Country | IP | City | ISP | Status |
|---------|-----|------|-----|--------|
| US | 216.237.240.39 | Mountain Village, Colorado | Mountain Village Town Of | ✅ Working |
| UK | 81.131.128.12 | Plymouth, England | British Telecommunications | ✅ Working |
| CA | 184.145.74.29 | Toronto, Ontario | Bell Canada | ✅ Working |
| DE | 87.164.189.72 | Amberg, Bavaria | Deutsche Telekom | ✅ Working |
| FR | 86.252.163.42 | Saint-Denis | Orange S.A. | ✅ Working |
| AU | - | - | - | ❌ Failed |
| JP | 106.167.79.134 | Machida, Tokyo | KDDI | ✅ Working |
| NL | 82.217.161.223 | Heerlen, Limburg | Vodafone Libertel | ✅ Working |

## Format
Username: `api-{COUNTRY}` (e.g., `api-US`, `api-UK`, `api-CA`)
Password: API key

## US is the best choice
- Lowest latency from our sandbox (US-based)
- AWS is a US company, US IPs are most "natural" for AWS accounts
- Residential ISPs look most legitimate

## Current Problem
Even with US residential proxy, ERR-837 still occurs after Name submission on profile.aws.amazon.com.

## Possible Causes of ERR-837
1. AWS detects proxy/VPN even for residential IPs
2. Browser fingerprint is too automated
3. Form submission is too fast (no human-like delays)
4. Missing browser headers/fingerprint data

## Solutions to Try
1. Add human-like delays between form submissions (3-5 seconds)
2. Add mouse movement simulation before clicking
3. Use a more realistic user agent with full fingerprint
4. Try different US residential IPs (each connection gets a different IP)
5. Add `--disable-blink-features=AutomationControlled` flag
6. Try without proxy but with stealth mode
