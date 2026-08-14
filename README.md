# Kiro Builder ID — Account Creator Bot V8

Automated AWS Builder ID account creation for Kiro with panel integration.

## V8 Changelog

| Fix/Feature | Description |
|-------------|-------------|
| **Loop Bug Fix** | Continue button max 2 clicks (was 5), prevents infinite loop |
| **post-name-submit State** | New state detection — when name field has value but page won't advance, forces restart instead of re-clicking |
| **fake.legal Support** | Disposable email provider with 4 domains (fake.legal, imgui.de, pulsewebmenu.de, gooncraft.de) |
| **Anti-Ban Gaps** | Random 2-8 min delay between accounts (configurable) |
| **Daily Limit** | File-based daily counter (default 500/day), auto-resets at midnight |
| **Unlimited Mode** | `--count 0` for unlimited (respects daily limit) |
| **Allow Access Fix** | Panel add clicks "Allow access" instead of "Deny access" |
| **PortalSignInError Fix** | Detects AWS 500 error, forces page reload + fresh proxy |
| **SPA Timeout Fix** | 30s hard reload + 60s full retry for blank pages |

## Quick Start

```bash
# 1. Install dependencies
pip install camoufox[geoip] playwright-stealth cloakbrowser

# 2. Set proxy environment variables
export PROXYRISE_SERVER="socks5://your-proxy-server:port"
export PROXYRISE_KEY="your-proxy-key"

# 3. Run (interactive mode - prompts for everything)
python3 run_bot.py

# 4. Run with arguments
python3 run_bot.py -p "https://your-panel.com" -w "panel-pass" -d "havenhaus.in" -c "us,no,se" --count 10 --headless
```

## CLI Options

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--panel` | `-p` | Panel URL | (prompt) |
| `--password` | `-w` | Panel password | (prompt) |
| `--domain` | `-d` | Catch-all domain(s) | (prompt) |
| `--country` | `-c` | Proxy country(s) | (prompt) |
| `--count` | | Number of accounts (0 = unlimited) | (prompt) |
| `--daily-limit` | | Max accounts per day (0 = unlimited) | 500 |
| `--min-gap` | | Min seconds between accounts (anti-ban) | 120 |
| `--max-gap` | | Max seconds between accounts (anti-ban) | 480 |
| `--headless` | | Run without browser UI | False |
| `--visible` | | Show browser window | False |
| `--max-retries-per-acc` | | Max retry attempts | 50 |
| `--no-proxy` | | Skip proxy (use VPN) | False |
| `--opera` | | Opera VPN cycling mode | False |
| `--stats` | | Show DB statistics | False |
| `--verify-panel` | | Verify in panel after add | False |
| `--mail-provider` | | Mail provider: gsuite_imap, shiromail, yydsmail, fake_legal | gsuite_imap |
| `--fake-legal-domain` | | Domain for fake.legal: fake.legal, imgui.de, pulsewebmenu.de, gooncraft.de | fake.legal |

## Usage Examples

### Interactive Mode (Recommended)
```bash
python3 run_bot.py
# Will prompt for: Panel URL, Password, Domain, Country, Count
```

### Quick Mode (10 accounts)
```bash
python3 run_bot.py -p "https://rd63vjg.abc-tunnel.us" -w "741085209630" -d "havenhaus.in" -c "us,no,se" --count 10 --headless
```

### Unlimited Mode (Daily Limit 500)
```bash
python3 run_bot.py -p "https://your-panel.com" --count 0 --daily-limit 500 --headless
```

### Custom Anti-Ban Gaps (2-8 min between accounts)
```bash
python3 run_bot.py -p "https://your-panel.com" --count 10 --min-gap 120 --max-gap 480 --headless
```

### fake.legal Mail Provider (Disposable Emails)
```bash
python3 run_bot.py -p "https://your-panel.com" --mail-provider fake_legal --fake-legal-domain imgui.de --count 5 --headless
```

### Opera VPN Mode (No Proxy)
```bash
python3 run_bot.py -p "https://rd63vjg.abc-tunnel.us" --opera --count 5
```

## Error Recovery

The bot automatically handles:

| Error | Recovery Action |
|-------|----------------|
| AWS portalSignInError (500) | Full rotation: OS + viewport + preset + slow profile |
| SPA blank page | Page reload + OS rotation + new proxy |
| Post-name-submit stuck | Force restart with new proxy |
| Continue loop (max 2 clicks) | Force restart instead of infinite clicking |
| Cloudflare challenge | OS rotation + preset change |
| AWS WAF/JS block | Slow profile + preset change |
| Datacenter IP | Slow profile |
| Rate limiting | Slow profile |
| 403 Forbidden | Full rotation |

## Proxy Setup

### ProxyRise (Residential)
```bash
export PROXYRISE_SERVER="socks5://172.65.145.196:3389"
export PROXYRISE_KEY="your-key-here"
```

### Multi-Country Rotation
```bash
python3 run_bot.py -c "us,no,se,fr" --count 10
```

## Output Files

- **Credentials**: `kiro_accounts.csv` (name, email, password, panel URL, timestamp)
- **Screenshots**: `screenshots/` directory
- **Learning DB**: `learning.db` (remembers what configs work)

## Tips

1. **macOS config works best** — prefers macOS over Windows/Linux
2. **Non-US countries** (Norway, Sweden, France) have better success rates
3. **Multiple domains** improve success — use comma-separated list
4. **Patience** — each account takes 5-10 minutes on average
5. **Retry is automatic** — the bot will keep trying with different configs
6. **Anti-ban gaps** prevent instant-ban detection by AWS (2-8 min random delay)
7. **Daily limit** prevents over-creation — defaults to 500/day

## File Structure

```
├── run_bot.py          # Main bot (CLI + multi-account + anti-ban)
├── kiro_acc_creator.py # Panel add flow (device auth, allow access)
├── mail_providers/     # Email providers
│   ├── fake_legal.py   # fake.legal disposable email (NEW)
│   ├── gsuite_imap.py
│   ├── shiromail.py
│   └── yydsmail.py
├── kiro_accounts.csv   # Created accounts
├── learning.db         # Anti-ban learning database
├── onrender_pool.json  # Proxy pool
├── cloakbrowser/       # Browser fingerprinting
├── requirements.txt
└── README.md
```
