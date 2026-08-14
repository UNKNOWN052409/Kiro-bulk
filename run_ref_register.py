"""Run the reference kiro-register-en flow headlessly and export to the gateway.

Usage:
  python run_ref_register.py <index>
Expects gmail_oauth_provider.GmailOAuthProvider + kiro_register.register available.
Writes kiro_creds/kiro_new<index>.json (gateway format) + appends credentials.json.
"""
import json
import sys
import time
from pathlib import Path

import asyncio

_BOT = Path(r"C:\Users/Unkno/Videos/New folder/with some fixes\kiro_bot_updated")
sys.path.insert(0, str(_BOT))

GATEWAY = Path(r"C:\Users\Unkno\Videos\New folder\new try")
CREDS_DIR = GATEWAY / "kiro_creds"
CREDS_JSON = GATEWAY / "credentials.json"

import logging as _lg
# silence emoji logging from mail_reader/gmail_oauth
for _n in list(_lg.root.manager.loggerDict):
    _lg.getLogger(_n).disabled = True
_lg.StreamHandler.emit = lambda self, *a, **k: None


def export(account, index):
    if not account or not account.get("refreshToken"):
        print("[!] no refreshToken in account result")
        return False
    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    email = account.get("email") or f"acct_{index}"
    fname = f"kiro_new{str(index).zfill(3)}.json"
    fpath = CREDS_DIR / fname
    acc = {
        "refreshToken": account["refreshToken"],
        "accessToken": account.get("accessToken", ""),
        "clientId": account.get("clientId", ""),
        "clientSecret": account.get("clientSecret", ""),
        "region": account.get("region", "us-east-1"),
        "startUrl": "https://view.awsapps.com/start/",
        "authMethod": account.get("authMethod", "IdC"),
        "provider": account.get("provider", "BuilderId"),
        "expiresAt": account.get("expiresAt", ""),
    }
    json.dump(acc, open(fpath, "w", encoding="utf-8"), indent=2)
    existing = []
    if CREDS_JSON.exists():
        try:
            existing = json.load(open(CREDS_JSON, encoding="utf-8"))
        except Exception:
            existing = []
    if not isinstance(existing, list):
        existing = []
    if not any(str(e.get("path")) == str(fpath) for e in existing if isinstance(e, dict)):
        existing.append({
            "type": "json", "path": str(fpath), "enabled": True,
            "comment": f"Captured {email} via headless register",
        })
        json.dump(existing, open(CREDS_JSON, "w", encoding="utf-8"), indent=2)
    print(f"[+] Exported {fname} ({email}) -> credentials.json has {len(existing)} entries")
    return True


def main():
    index = sys.argv[1] if len(sys.argv) > 1 else "0"
    from gmail_oauth_provider import GmailOAuthProvider
    from kiro_register import register

    provider = GmailOAuthProvider(domain="havenhaus.in", length=10)
    # generate a fresh mailbox up front
    provider.create_mailbox()
    print(f"[*] Using mailbox: {provider.address}")

    result = asyncio.run(register(
        headless=True,
        auto_login=False,        # we export ourselves, don't inject into ~/.aws
        skip_onboard=True,
        mail_provider_instance=provider,
        log=print,
        cancel_check=None,
    ))

    if not result:
        print("[!] register() returned None")
        raise SystemExit(1)
    if result.get("incomplete"):
        print(f"[!] registration incomplete: {result.get('failReason')}")
        # still try to export if a token exists
    ok = export(result, index)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
