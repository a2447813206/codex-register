"""Full registration test: 1 account using config.json settings"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print(" FULL REGISTRATION TEST (1 account)")
print("=" * 60)

# Quick proxy check first
print("\n[Pre-check] Proxy connectivity...")
from curl_cffi import requests as cffi_requests

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), "r") as f:
    cfg = json.load(f)
import json

proxy = cfg.get("proxy", "")
print(f"  Proxy: {proxy}")
try:
    r = cffi_requests.get("https://httpbin.org/ip", proxies={"https": proxy, "http": proxy}, timeout=15, impersonate="chrome")
    print(f"  [OK] IP={r.json().get('origin','?')}")
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

print("\n[Pre-check] MailAPI bulk pool...")
bulk = cfg.get("mailapi_icu_bulk", [])
print(f"  Pool size: {len(bulk)}")
if bulk:
    print(f"  First email: {bulk[0]['email']}")

print("\n[Pre-check] Playwright + Sentinel token...")
try:
    from playwright_sentinel import generate_sentinel_token_playwright
    token = generate_sentinel_token_playwright("register", proxy=proxy)
    if token and len(str(token)) > 50:
        print(f"  [OK] Turnstile token len={len(str(token))}")
    else:
        print(f"  [WARN] Token short: {str(token)[:80] if token else 'empty'}")
except Exception as e:
    print(f"  [WARN] {type(e).__name__}: {e}")

# ---- RUN REGISTRATION ----
print("\n" + "=" * 60)
print(" STARTING REGISTRATION (1 account)")
print("=" * 60)

from config_loader import ConfigLoader
loader = ConfigLoader()
loader.run_batch(total_accounts=1, max_workers=1, proxy=proxy)

print("\n=== TEST COMPLETE ===")
