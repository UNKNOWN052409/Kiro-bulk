"""
Mail Automation Engine — Main Loop
====================================
Watches for new emails and applies automation rules.

Usage:
    python mail_automation.py              # Start the automation loop
    python mail_automation.py --once       # Run once, then exit
    python mail_automation.py --dry-run    # Process but don't send replies
"""

import time
import logging
import argparse
import sys
import json
import re
import requests
from datetime import datetime
from typing import List, Dict, Callable, Optional

from mail_config import (
    POLL_INTERVAL_SECONDS, INBOX_FOLDER, MAX_EMAILS_PER_POLL,
    LOG_FILE, AUTOMATION_RULES,
    GMAIL_EMAIL
)
from mail_reader import fetch_emails, mark_email_read
from mail_sender import send_email, send_reply

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)





# ══════════════════════════════════════════════════════════════════════════════
#  MAIN AUTOMATION LOOP
# ══════════════════════════════════════════════════════════════════════════════
def process_once(dry_run: bool = False) -> int:
    """Fetch unread emails and apply rules. Returns number of emails processed."""
    log.info("🔄 Checking for new emails...")

    try:
        emails = fetch_emails(unread_only=True, mark_as_read=False)
    except Exception as e:
        log.error(f"❌ Failed to fetch emails: {e}")
        return 0

    if not emails:
        return 0

    processed = 0
    for mail in emails:
        log.info(f"\n📧 Processing: '{mail['subject']}' from {mail['from']}")
        action_taken = False

        for rule in AUTOMATION_RULES:
            if matches_rule(mail, rule):
                action_taken = apply_rule(mail, rule, dry_run=dry_run)
                if action_taken:
                    break  # Only apply first matching rule

        if not action_taken:
            log.info("  → No matching rule (email logged only)")

        # Mark as read after processing
        if not dry_run:
            mark_email_read(mail["uid"])

        processed += 1

    return processed


def run_loop(dry_run: bool = False):
    """Run the automation loop indefinitely."""
    log.info("═" * 60)
    log.info("🚀 Mail Automation Engine STARTED")
    log.info(f"   Mailbox : {GMAIL_EMAIL}")
    log.info(f"   Interval: every {POLL_INTERVAL_SECONDS} seconds")
    log.info(f"   Rules   : {len(AUTOMATION_RULES)} configured")
    if dry_run:
        log.info("   Mode    : DRY RUN (no emails will be sent)")
    log.info("═" * 60)
    log.info("Press Ctrl+C to stop.\n")

    try:
        while True:
            count = process_once(dry_run=dry_run)
            if count > 0:
                log.info(f"✅ Processed {count} email(s)")
            next_check = datetime.now().strftime("%H:%M:%S")
            log.info(f"💤 Sleeping {POLL_INTERVAL_SECONDS}s (next check ~{next_check})")
            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log.info("\n🛑 Automation stopped by user")


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mail Automation Engine")
    parser.add_argument("--once",    action="store_true", help="Process once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Process but don't send replies")
    args = parser.parse_args()

    if args.once:
        count = process_once(dry_run=args.dry_run)
        print(f"\n✅ Done. Processed {count} email(s).")
    else:
        run_loop(dry_run=args.dry_run)
