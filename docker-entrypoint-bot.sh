#!/bin/bash
set -e

# Start Xvfb for headed browser mode
rm -f /tmp/.X99-lock 2>/dev/null || true
Xvfb :99 -screen 0 1920x1080x24 -ac &
export DISPLAY=:99
sleep 2

# Clean stale browser profile locks
rm -rf /app/automation/automation/browser_profile/SingletonLock \
       /app/automation/automation/browser_profile/SingletonSocket \
       /app/automation/automation/browser_profile/SingletonCookie 2>/dev/null || true

# Defaults
ACCOUNT_COUNT=${COUNT:-99999}
DOMAIN=${DOMAIN:-fake.legal}
COUNTRY=${COUNTRY:-us}
MAIL_PROVIDER=${MAIL_PROVIDER:-fake_legal}
PANELS=${PANELS:-}

echo "=== Kiro Bot ==="
echo "Panels:   ${PANELS:-single-panel mode}"
echo "Accounts: ${ACCOUNT_COUNT}"
echo "Domain:   ${DOMAIN}"
echo "Country:  ${COUNTRY}"
echo "Mail:     ${MAIL_PROVIDER}"
echo "==============="

cd /app
mkdir -p /app/output/screenshots

# Build args
EXTRA_ARGS=""
[ -n "$MAIL_PROVIDER" ] && EXTRA_ARGS="$EXTRA_ARGS --mail-provider $MAIL_PROVIDER"
[ -n "$DOMAIN" ] && EXTRA_ARGS="$EXTRA_ARGS --domain $DOMAIN"
[ -n "$COUNTRY" ] && EXTRA_ARGS="$EXTRA_ARGS --country $COUNTRY"

# Multi-panel mode: --panels file
if [ -n "$PANELS" ] && [ -f "$PANELS" ]; then
    exec python3 run_bot.py \
        --panels "$PANELS" \
        --count "$ACCOUNT_COUNT" \
        --headless \
        $EXTRA_ARGS
else
    # Single panel mode (fallback)
    PANEL_URL=${PANEL_URL:-https://rd63vjg.abc-tunnel.us}
    PANEL_PASS=${PANEL_PASS:-741089410561023}
    exec python3 run_bot.py \
        -p "$PANEL_URL" \
        -w "$PANEL_PASS" \
        --count "$ACCOUNT_COUNT" \
        --headless \
        $EXTRA_ARGS
fi
