"""
Sentinel SDK 版本动态探测模块

自动探测 OpenAI Sentinel SDK 的当前版本号，避免硬编码。
支持两种探测方式：
  1. 纯 HTTP：请求 sdk.js 的 302 重定向获取版本号
  2. Playwright：加载 frame.html 从页面中提取版本号

结果缓存到内存 + 磁盘文件，避免频繁请求。
"""

import json
import os
import re
import threading
import time

_lock = threading.Lock()
_cached_version = None
_cached_time = 0
_CACHE_TTL = 3600  # 1 小时缓存
_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sentinel_sdk_version.json")

SENTINEL_BASE = "https://sentinel.openai.com"
SDK_LOADER_URL = f"{SENTINEL_BASE}/backend-api/sentinel/sdk.js"
FRAME_BASE_URL = f"{SENTINEL_BASE}/backend-api/sentinel/frame.html"


def _load_disk_cache():
    """从磁盘缓存文件加载"""
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r") as f:
                data = json.load(f)
            ts = data.get("timestamp", 0)
            ver = data.get("version", "")
            if ver and (time.time() - ts) < _CACHE_TTL:
                return ver
    except Exception:
        pass
    return None


def _save_disk_cache(version):
    """保存到磁盘缓存"""
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump({"version": version, "timestamp": time.time()}, f)
    except Exception:
        pass


def _probe_via_http(proxy=None):
    """方式一：HEAD/GET 请求 sdk.js，跟踪 302 重定向提取版本号"""
    try:
        from curl_cffi import requests as curl_requests
        session = curl_requests.Session(verify=False)
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}

        # sdk.js 会 302 → /sentinel/<version>/sdk.js
        resp = session.get(SDK_LOADER_URL, allow_redirects=True, timeout=15)
        final_url = str(resp.url)
        # 从最终 URL 提取版本号: /sentinel/<version>/sdk.js
        m = re.search(r"/sentinel/([a-zA-Z0-9]+)/sdk\.js", final_url)
        if m:
            ver = m.group(1)
            print(f"[SentinelSDK] HTTP 探测成功: version={ver}")
            return ver

        # 从响应体中查找版本号（sdk.js 可能内联引用自身版本）
        text = resp.text[:5000] if resp.text else ""
        m = re.search(r"/sentinel/([a-zA-Z0-9]{10,})/sdk\.js", text)
        if m:
            ver = m.group(1)
            print(f"[SentinelSDK] HTTP 从响应体提取: version={ver}")
            return ver
    except Exception as e:
        print(f"[SentinelSDK] HTTP 探测失败: {e}")
    return None


def _probe_via_frame_html(proxy=None):
    """方式二：请求 frame.html（不带 sv 参数），从 HTML 中提取 SDK 版本"""
    try:
        from curl_cffi import requests as curl_requests
        session = curl_requests.Session(verify=False)
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}

        resp = session.get(FRAME_BASE_URL, timeout=15)
        text = resp.text[:10000] if resp.text else ""
        # frame.html 通常引用 sdk.js 或 frame.html?sv=<version>
        m = re.search(r"/sentinel/([a-zA-Z0-9]{10,})/sdk\.js", text)
        if m:
            ver = m.group(1)
            print(f"[SentinelSDK] frame.html 提取: version={ver}")
            return ver
        m = re.search(r"sv=([a-zA-Z0-9]{10,})", text)
        if m:
            ver = m.group(1)
            print(f"[SentinelSDK] frame.html sv= 提取: version={ver}")
            return ver
    except Exception as e:
        print(f"[SentinelSDK] frame.html 探测失败: {e}")
    return None


def _probe_via_playwright(proxy=None):
    """方式三：Playwright 加载 frame.html，从网络请求中捕获 SDK 版本"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    version = None
    try:
        with sync_playwright() as p:
            launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-gpu"]}
            if proxy:
                norm = proxy.strip()
                if norm.startswith("socks5h://"):
                    norm = "socks5://" + norm[len("socks5h://"):]
                launch_args["proxy"] = {"server": norm}

            browser = p.chromium.launch(**launch_args)
            context = browser.new_context()

            captured = {}

            def on_response(response):
                url = response.url
                m = re.search(r"/sentinel/([a-zA-Z0-9]{10,})/sdk\.js", url)
                if m:
                    captured["version"] = m.group(1)

            page = context.new_page()
            page.on("response", on_response)

            # 不带 sv 参数访问 frame.html，让它自己加载最新 SDK
            page.goto(FRAME_BASE_URL, wait_until="load", timeout=30000)
            page.wait_for_timeout(3000)

            version = captured.get("version")

            # 如果网络捕获没拿到，从页面 JS 中提取
            if not version:
                try:
                    version = page.evaluate("""() => {
                        // 从 script 标签中提取
                        const scripts = document.querySelectorAll('script[src]');
                        for (const s of scripts) {
                            const m = s.src.match(/\\/sentinel\\/([a-zA-Z0-9]{10,})\\/sdk\\.js/);
                            if (m) return m[1];
                        }
                        // 从 performance entries 中提取
                        const entries = performance.getEntriesByType('resource');
                        for (const e of entries) {
                            const m = e.name.match(/\\/sentinel\\/([a-zA-Z0-9]{10,})\\/sdk\\.js/);
                            if (m) return m[1];
                        }
                        return null;
                    }""")
                except Exception:
                    pass

            context.close()
            browser.close()

        if version:
            print(f"[SentinelSDK] Playwright 探测成功: version={version}")
    except Exception as e:
        print(f"[SentinelSDK] Playwright 探测失败: {e}")

    return version


def get_sentinel_sdk_version(proxy=None, force_refresh=False):
    """获取当前 Sentinel SDK 版本号（带缓存）

    探测顺序: 磁盘缓存 → HTTP 302 → frame.html → Playwright
    """
    global _cached_version, _cached_time

    # 内存缓存
    if not force_refresh and _cached_version and (time.time() - _cached_time) < _CACHE_TTL:
        return _cached_version

    with _lock:
        # double check
        if not force_refresh and _cached_version and (time.time() - _cached_time) < _CACHE_TTL:
            return _cached_version

        # 磁盘缓存
        if not force_refresh:
            ver = _load_disk_cache()
            if ver:
                _cached_version = ver
                _cached_time = time.time()
                print(f"[SentinelSDK] 使用磁盘缓存: {ver}")
                return ver

        # 逐级探测
        for probe_fn in [_probe_via_http, _probe_via_frame_html, _probe_via_playwright]:
            ver = probe_fn(proxy=proxy)
            if ver:
                _cached_version = ver
                _cached_time = time.time()
                _save_disk_cache(ver)
                return ver

        # 全部失败，返回 None（调用方需处理）
        print("[SentinelSDK] 所有探测方式均失败，无法获取 SDK 版本")
        return None


def get_sentinel_frame_url(proxy=None):
    """获取带版本号的 sentinel frame URL"""
    ver = get_sentinel_sdk_version(proxy=proxy)
    if ver:
        return f"{FRAME_BASE_URL}?sv={ver}"
    # 不带版本号也能访问，服务端会自动重定向
    return FRAME_BASE_URL


def get_sentinel_sdk_url(proxy=None):
    """获取带版本号的 sentinel SDK JS URL"""
    ver = get_sentinel_sdk_version(proxy=proxy)
    if ver:
        return f"{SENTINEL_BASE}/sentinel/{ver}/sdk.js"
    return f"{SENTINEL_BASE}/backend-api/sentinel/sdk.js"
