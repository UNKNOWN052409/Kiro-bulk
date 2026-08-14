FROM python:3.12-slim

# System deps for Chromium (CloakBrowser) + Firefox (Camoufox) + Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 \
    libxcb1 libxext6 libxshmfence1 \
    libglib2.0-0 libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 libxss1 libxtst6 fonts-liberation \
    fonts-noto-color-emoji fonts-unifont fonts-freefont-ttf \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    xvfb xdotool \
    curl ca-certificates git \
    # Firefox deps for Camoufox
    libdbus-glib-1-2 libxt6 \
    wget gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CloakBrowser (local package)
COPY CloakBrowser/ /app/CloakBrowser/
RUN cd /app/CloakBrowser && pip install --no-cache-dir ".[geoip]"

# Install Camoufox and other Python deps
RUN pip install --no-cache-dir \
    "camoufox[geoip]" \
    playwright-stealth \
    faker \
    pyinstaller \
    curl_cffi \
    playwright \
    cryptography \
    requests \
    httpx

# Install Playwright browsers (Firefox for Camoufox, Chromium for CloakBrowser)
RUN python -m playwright install firefox && \
    python -m playwright install chromium

# Pre-download Camoufox binary
RUN python -c "from camoufox.sync_api import Camoufox; print('Camoufox binary ready')" || true

# Copy bot files
COPY run_bot.py /app/run_bot.py
COPY mail_providers/ /app/mail_providers/
COPY requirements.txt /app/requirements.txt

# Copy automation directory (mail_reader, mail_config, gmail_oauth, etc.)
COPY automation/automation/ /app/automation/automation/

# Create required directories
RUN mkdir -p /app/automation/automation/screenshots \
    /app/automation/automation/browser_profile

# Set display for Xvfb
ENV DISPLAY=:99
ENV OUTPUT_DIR=/app/output
RUN mkdir -p /app/output/screenshots

# Entry script that starts Xvfb then runs the bot
COPY docker-entrypoint-bot.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
