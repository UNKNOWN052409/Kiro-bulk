from flask import Flask, render_template, request, jsonify
from mail_reader import fetch_emails
from mail_sender import send_email
import logging
import time
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ── In-memory cache ────────────────────────────────────────────────────────────
# Avoids hitting IMAP on every request — cache expires after 60 seconds
_email_cache = {
    "emails": [],
    "fetched_at": 0,
    "ttl": 60  # seconds before cache expires
}

def get_cached_emails(force_refresh=False):
    """Return cached emails, refreshing if expired or forced."""
    now = time.time()
    age = now - _email_cache["fetched_at"]

    if force_refresh or age > _email_cache["ttl"] or not _email_cache["emails"]:
        app.logger.info("Fetching fresh emails from IMAP...")
        raw = fetch_emails(unread_only=False, limit=50, mark_as_read=False)
        # Serialize dates
        for e in raw:
            if e.get("date"):
                e["date"] = e["date"].isoformat()
            else:
                e["date"] = ""
        _email_cache["emails"] = raw
        _email_cache["fetched_at"] = now
        app.logger.info(f"Cached {len(raw)} emails.")
    else:
        app.logger.info(f"Returning cached emails (age: {age:.1f}s)")

    return _email_cache["emails"]


def filter_by_time(emails, window: str):
    """
    Filter emails by time window.
    window: 'all' | 'today' | '1h' | '3h'
    """
    if window == "all":
        return emails

    now = datetime.now(timezone.utc)
    if window == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif window == "1h":
        cutoff = now - timedelta(hours=1)
    elif window == "3h":
        cutoff = now - timedelta(hours=3)
    else:
        return emails

    filtered = []
    for e in emails:
        if not e.get("date"):
            continue
        try:
            # Parse ISO date string
            d = datetime.fromisoformat(e["date"])
            # Make timezone-aware if naive
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d >= cutoff:
                filtered.append(e)
        except Exception:
            continue

    return filtered


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/emails")
def api_emails():
    """
    Fetch emails with optional time filter.
    Query params:
      ?filter=all|today|1h|3h   (default: all)
      ?refresh=1                 (force cache refresh)
    """
    window = request.args.get("filter", "all")
    force = request.args.get("refresh", "0") == "1"

    try:
        emails = get_cached_emails(force_refresh=force)
        filtered = filter_by_time(emails, window)
        return jsonify({
            "success": True,
            "emails": filtered,
            "total": len(emails),
            "shown": len(filtered),
            "cached_age": round(time.time() - _email_cache["fetched_at"]),
            "filter": window
        })
    except Exception as e:
        app.logger.error(f"Error fetching emails: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/send", methods=["POST"])
def api_send():
    data = request.json
    if not data or not data.get("to") or not data.get("subject") or not data.get("body"):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    try:
        success = send_email(
            to=data["to"],
            subject=data["subject"],
            body_html=data["body"],
            body_text=data["body"]
        )
        if success:
            # Invalidate cache so sent email shows up on refresh
            _email_cache["fetched_at"] = 0
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to send. Check logs."}), 500
    except Exception as e:
        app.logger.error(f"Error sending email: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
