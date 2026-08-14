#!/usr/bin/env python3
"""
Proxy CLI - Manage residential proxies via ProxyRise API
"""
import argparse
import json
import os
import sys
import requests

API_KEY = "pgw-d890748b9e9c734c66a3c1a327fd1db84724cad6cbbe440d"
PROXY_ENDPOINT = "gate.smartproxy.com:7000"

CONFIG_DIR = os.path.expanduser("~/.proxy_cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

def load_settings():
    """Load saved settings or use defaults."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            settings = json.load(f)
            return settings.get("api_key", API_KEY), settings.get("endpoint", PROXY_ENDPOINT)
    return API_KEY, PROXY_ENDPOINT

def save_settings(api_key, endpoint):
    """Save API key and endpoint to config."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"api_key": api_key, "endpoint": endpoint}, f, indent=2)

def get_rotating_proxy(country="us"):
    """Get rotating residential proxy configuration."""
    api_key, endpoint = load_settings()
    return {
        "http": f"http://res-{country}:{api_key}@{endpoint}",
        "https": f"http://res-{country}:{api_key}@{endpoint}",
    }

def get_sticky_proxy(session_id, country="us"):
    """Get sticky session residential proxy configuration."""
    api_key, endpoint = load_settings()
    return {
        "http": f"http://res-{country}-sid-{session_id}:{api_key}@{endpoint}",
        "https": f"http://res-{country}-sid-{session_id}:{api_key}@{endpoint}",
    }

def get_proxy_string(country="us"):
    """Get proxy as string for Selenium."""
    api_key, endpoint = load_settings()
    return f"http://res-{country}:{api_key}@{endpoint}"

def test_proxy(proxies, url="https://httpbin.org/ip"):
    """Test proxy connection and return IP info."""
    try:
        r = requests.get(url, proxies=proxies, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        return {"error": str(e)}

def save_proxy_config(proxies, name="default"):
    """Save proxy configuration to file."""
    config = {
        "name": name,
        "http": proxies["http"],
        "https": proxies["https"],
    }
    config_dir = os.path.expanduser("~/.proxy_cli")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, f"{name}.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    return config_path

def load_proxy_config(name="default"):
    """Load proxy configuration from file."""
    config_path = os.path.join(os.path.expanduser("~/.proxy_cli"), f"{name}.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
    return None

def list_configs():
    """List all saved proxy configurations."""
    config_dir = os.path.expanduser("~/.proxy_cli")
    if not os.path.exists(config_dir):
        return []
    configs = []
    for f in os.listdir(config_dir):
        if f.endswith(".json"):
            with open(os.path.join(config_dir, f)) as fp:
                configs.append(json.load(fp))
    return configs

def main():
    parser = argparse.ArgumentParser(description="Residential Proxy CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Rotating proxy
    rotate_parser = subparsers.add_parser("rotate", help="Get rotating residential proxy")
    rotate_parser.add_argument("--country", default="us", help="Country code (default: us)")
    rotate_parser.add_argument("--test", action="store_true", help="Test the proxy")
    rotate_parser.add_argument("--save", help="Save config with name")

    # Sticky proxy
    sticky_parser = subparsers.add_parser("sticky", help="Get sticky session proxy")
    sticky_parser.add_argument("session_id", help="Session ID for sticky proxy")
    sticky_parser.add_argument("--country", default="us", help="Country code (default: us)")
    sticky_parser.add_argument("--test", action="store_true", help="Test the proxy")
    sticky_parser.add_argument("--save", help="Save config with name")

    # Test proxy
    test_parser = subparsers.add_parser("test", help="Test a saved proxy config")
    test_parser.add_argument("name", nargs="?", default="default", help="Config name (default: default)")

    # List configs
    subparsers.add_parser("list", help="List saved proxy configurations")

    # Show config
    show_parser = subparsers.add_parser("show", help="Show proxy configuration")
    show_parser.add_argument("name", nargs="?", default="default", help="Config name (default: default)")

    # Settings
    settings_parser = subparsers.add_parser("settings", help="View/edit API key and endpoint")
    settings_parser.add_argument("--api-key", help="Update API key")
    settings_parser.add_argument("--endpoint", help="Update proxy endpoint")

    args = parser.parse_args()

    if args.command == "rotate":
        proxies = get_rotating_proxy(args.country)
        print(f"Rotating {args.country.upper()} Proxy:")
        print(f"  HTTP:  {proxies['http']}")
        print(f"  HTTPS: {proxies['https']}")

        if args.test:
            print("\nTesting proxy...")
            result = test_proxy(proxies)
            print(f"Result: {json.dumps(result, indent=2)}")

        if args.save:
            path = save_proxy_config(proxies, args.save)
            print(f"\nSaved to: {path}")

    elif args.command == "sticky":
        proxies = get_sticky_proxy(args.session_id, args.country)
        print(f"Sticky {args.country.upper()} Proxy (session: {args.session_id}):")
        print(f"  HTTP:  {proxies['http']}")
        print(f"  HTTPS: {proxies['https']}")

        if args.test:
            print("\nTesting proxy...")
            result = test_proxy(proxies)
            print(f"Result: {json.dumps(result, indent=2)}")

        if args.save:
            path = save_proxy_config(proxies, args.save)
            print(f"\nSaved to: {path}")

    elif args.command == "test":
        config = load_proxy_config(args.name)
        if not config:
            print(f"Config '{args.name}' not found. Run 'list' to see available configs.")
            sys.exit(1)
        proxies = {"http": config["http"], "https": config["https"]}
        print(f"Testing config: {args.name}")
        result = test_proxy(proxies)
        print(f"Result: {json.dumps(result, indent=2)}")

    elif args.command == "list":
        configs = list_configs()
        if not configs:
            print("No saved configurations.")
        else:
            print("Saved Proxy Configurations:")
            for c in configs:
                print(f"  - {c['name']}")

    elif args.command == "show":
        config = load_proxy_config(args.name)
        if not config:
            print(f"Config '{args.name}' not found.")
            sys.exit(1)
        print(f"Config: {config['name']}")
        print(f"  HTTP:  {config['http']}")
        print(f"  HTTPS: {config['https']}")

    elif args.command == "settings":
        api_key, endpoint = load_settings()
        if args.api_key or args.endpoint:
            new_key = args.api_key or api_key
            new_endpoint = args.endpoint or endpoint
            save_settings(new_key, new_endpoint)
            print("Settings updated!")
        print(f"\nCurrent Settings:")
        print(f"  API Key:    {api_key}")
        print(f"  Endpoint:   {endpoint}")

if __name__ == "__main__":
    main()