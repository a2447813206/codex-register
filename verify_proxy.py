"""Quick proxy verification: HTTP + Playwright + Turnstile"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Read config directly
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), "r") as f:
    cfg = json.load(f)

proxy = cfg.get("proxy", "")
print(f"=== Proxy Verification ===")
print(f"Proxy: {proxy or '(empty)'}")
if not proxy:
    print("WARNING: No proxy configured in config.json!")
print()

# Step 1: curl_cffi HTTP test
print("[Step 1] curl_cffi HTTP request...")
try:
    from curl_cffi import requests as cffi_requests
    if proxy:
        r = cffi_requests.get("https://httpbin.org/ip", proxies={"https": proxy, "http": proxy}, timeout=15, impersonate="chrome")
    else:
        r = cffi_requests.get("https://httpbin.org/ip", timeout=15, impersonate="chrome")
    print(f"  [OK] HTTP | status={r.status_code} | IP={r.json().get('origin', '?')}")
except Exception as e:
    print(f"  [FAIL] HTTP error: {e}")

# Step 2: Playwright browser test (only if proxy set)
if proxy:
    print("\n[Step 2] Playwright browser launch with proxy auth...")
    try:
        from playwright_sentinel import _parse_proxy, _get_browser, _close_browser
        parsed = _parse_proxy(proxy)
        print(f"  Parsed: server={parsed.get('server','?')}, user={parsed.get('username','(none)')}")
        browser = _get_browser(proxy)
        page = browser.new_page()
        r = page.goto("https://httpbin.org/ip", timeout=20000)
        text = page.inner_text("body")
        print(f"  [OK] Playwright | status={r} | IP={text.strip()}")
        page.close()
        _close_browser()
    except Exception as e:
        print(f"  [FAIL] Playwright error: {type(e).__name__}: {e}")

# Step 3: Turnstile Token generation test
if proxy:
    print("\n[Step 3] Sentinel Turnstile Token generation...")
    try:
        from playwright_sentinel import generate_sentinel_token_playwright
        token = generate_sentinel_token_playwright("register", proxy=proxy)
        if token and len(str(token)) > 50:
            print(f"  [OK] Turnstile | token_len={len(str(token))}")
        else:
            print(f"  [WARN] Token abnormal: len={len(str(token)) if token else 0}")
            print(f"  token preview: {str(token)[:100] if token else '(empty)'}")
    except Exception as e:
        print(f"  [WARN] Error: {type(e).__name__}: {e}")

print("\n=== Done ===")
