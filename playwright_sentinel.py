"""
Playwright-based Sentinel Token Generator

使用无头浏览器加载 SentinelSDK，执行真实的 Turnstile 挑战，
生成包含完整 p/t/c 字段的 sentinel token。

仅在注册流程需要时启动浏览器，其余步骤仍走纯 HTTP。
"""

import json
import os
import threading
import time
import traceback

# 全局浏览器实例（懒加载，跨线程共享）
_pw_instance = None  # sync_playwright() 返回值
_browser = None
_browser_lock = threading.Lock()
_browser_proxy = None  # 记录当前 browser 使用的 proxy
_context_local = threading.local()

SDK_WAIT_TIMEOUT = int(os.environ.get("SENTINEL_SDK_WAIT_MS", "60000"))
SDK_LOAD_WAIT = int(os.environ.get("SENTINEL_LOAD_WAIT_MS", "10000"))
MAX_RETRIES = int(os.environ.get("SENTINEL_MAX_RETRIES", "2"))


def _auto_detect_proxy():
    """自动检测可用代理（SingBox 本地代理 / 环境变量）"""
    # 1. SingBox 本地代理
    try:
        from src.services.singbox import is_enabled, get_singbox_proxy
        if is_enabled():
            proxy = get_singbox_proxy()
            print(f"[Playwright] 自动检测到 SingBox 代理: {proxy}")
            return proxy
    except Exception:
        pass

    # 2. 环境变量
    for key in ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]:
        val = os.environ.get(key, "").strip()
        if val:
            return val

    return None


def _get_frame_url():
    """动态获取 sentinel frame URL（优先环境变量覆盖，否则自动探测版本）"""
    env_url = os.environ.get("SENTINEL_FRAME_URL", "")
    if env_url:
        return env_url
    try:
        from sentinel_sdk_version import get_sentinel_frame_url
        return get_sentinel_frame_url()
    except Exception:
        # 探测失败时回退到不带版本号的 URL（服务端会自动处理）
        return "https://sentinel.openai.com/backend-api/sentinel/frame.html"


def _parse_proxy(proxy):
    """解析代理地址为 Playwright 支持的格式

    支持: user:pass@host:port / http://user:pass@host:port / socks5://user:pass@host:port
    返回: {"server": ..., "username": ..., "password": ...} 或 None
    """
    if not proxy:
        return None
    proxy = proxy.strip()
    # socks5h:// -> 改为 socks5://（Playwright 不支持 socks5h）
    if proxy.startswith("socks5h://"):
        proxy = "socks5://" + proxy[len("socks5h://"):]

    from urllib.parse import urlparse

    # 如果不带 scheme，默认 http
    if not re.match(r'^[a-z][a-z0-9+.-]*://', proxy, re.I):
        parsed = urlparse(f"http://{proxy}")
    else:
        parsed = urlparse(proxy)

    result = {
        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
    }
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    return result


import re


def _get_browser(proxy=None):
    """懒加载全局 Chromium 浏览器实例"""
    global _browser, _pw_instance, _browser_proxy

    # 解析代理（返回 dict 或 None）
    parsed_proxy = _parse_proxy(proxy) if proxy else None
    # 用原始字符串作为缓存 key（用于判断是否需要重建浏览器）
    norm_proxy = proxy.strip() if proxy else None

    # 已有浏览器且代理一致，直接返回
    if _browser and _browser.is_connected() and _browser_proxy == norm_proxy:
        return _browser

    with _browser_lock:
        # double-check
        if _browser and _browser.is_connected() and _browser_proxy == norm_proxy:
            return _browser

        # 关闭旧浏览器（代理变了或断开了）
        _close_browser_unlocked()

        from playwright.sync_api import sync_playwright
        _pw_instance = sync_playwright().start()

        # Turnstile 对 headless 检测严格，优先使用 headed 模式
        # 环境变量 SENTINEL_HEADLESS=1 可强制 headless
        use_headless = os.environ.get("SENTINEL_HEADLESS", "").strip() == "1"

        launch_args = {
            "headless": use_headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        # 非 headless 时最小化窗口避免干扰
        if not use_headless:
            launch_args["args"].append("--window-position=-9999,-9999")
            launch_args["args"].append("--window-size=1,1")

        if parsed_proxy:
            launch_args["proxy"] = parsed_proxy

        mode = "headless" if use_headless else "headed"
        print(f"[Playwright] 启动浏览器 ({mode}, proxy={norm_proxy or 'direct'})")
        _browser = _pw_instance.chromium.launch(**launch_args)
        _browser_proxy = norm_proxy
        return _browser


def _close_browser_unlocked():
    """关闭浏览器（调用者需持有 _browser_lock）"""
    global _browser, _pw_instance, _browser_proxy
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _pw_instance:
        try:
            _pw_instance.stop()
        except Exception:
            pass
        _pw_instance = None
    _browser_proxy = None


def _create_page(proxy=None, user_agent=None):
    """创建新的 context + page 并加载 sentinel frame，等待 SDK 就绪"""
    browser = _get_browser(proxy)

    ctx_opts = {
        "locale": "en-US",
        "viewport": {"width": 1920, "height": 1080},
        "java_script_enabled": True,
    }
    if user_agent:
        ctx_opts["user_agent"] = user_agent

    context = browser.new_context(**ctx_opts)

    # 反无头检测: 注入 stealth 脚本
    context.add_init_script("""
        // 隐藏 webdriver 标志
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        // 伪造 plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        // 伪造 languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        // Chrome runtime
        window.chrome = { runtime: {} };
        // 隐藏 permissions query 异常
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """)

    page = context.new_page()

    frame_url = _get_frame_url()
    print(f"[Playwright] 加载 sentinel frame: {frame_url[:80]}...")
    page.goto(frame_url, wait_until="load", timeout=120000)

    # 等待页面初始化
    print(f"[Playwright] 等待 SDK 加载 ({SDK_LOAD_WAIT}ms + polling)...")
    page.wait_for_timeout(SDK_LOAD_WAIT)

    # 等待 SentinelSDK 全局对象出现
    page.wait_for_function(
        "() => typeof window.SentinelSDK !== 'undefined' && window.SentinelSDK !== null",
        timeout=SDK_WAIT_TIMEOUT,
    )
    print("[Playwright] SentinelSDK 已就绪")
    return context, page


def _get_or_create_page(proxy=None, user_agent=None):
    """获取当前线程的 page，如果不存在或已关闭则新建"""
    page = getattr(_context_local, "page", None)
    ctx = getattr(_context_local, "context", None)

    if page and not page.is_closed():
        # 验证 SDK 仍然可用
        try:
            ok = page.evaluate("() => typeof window.SentinelSDK !== 'undefined'")
            if ok:
                return ctx, page
        except Exception:
            pass

    # 清理旧资源
    _cleanup_thread_page()

    ctx, page = _create_page(proxy=proxy, user_agent=user_agent)
    _context_local.page = page
    _context_local.context = ctx
    return ctx, page


def _cleanup_thread_page():
    """清理当前线程的 page/context"""
    ctx = getattr(_context_local, "context", None)
    if ctx:
        try:
            ctx.close()
        except Exception:
            pass
    _context_local.page = None
    _context_local.context = None


def generate_sentinel_token_playwright(flow, proxy=None, user_agent=None):
    """
    通过 Playwright 调用 SentinelSDK 生成完整 sentinel token。

    返回: JSON 字符串 (包含 p, t, c, flow 等字段)，失败返回 None。
    """
    # 如果没传 proxy，尝试自动获取（SingBox 模式 / 环境变量）
    if not proxy:
        proxy = _auto_detect_proxy()
    print(f"[Playwright Sentinel] flow={flow}, proxy={proxy or 'direct'}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ctx, page = _get_or_create_page(proxy=proxy, user_agent=user_agent)
            result = page.evaluate(
                """async (flow) => {
                    if (!window.SentinelSDK) throw new Error('SentinelSDK not loaded');
                    await window.SentinelSDK.init(flow);
                    const tok = await window.SentinelSDK.token(flow);
                    // tok 可能是字符串或对象，统一返回
                    if (typeof tok === 'string') {
                        // 检查是否是 JSON 字符串
                        try { JSON.parse(tok); return tok; } catch(e) { return tok; }
                    }
                    if (tok && typeof tok === 'object') {
                        return JSON.stringify(tok);
                    }
                    return tok;
                }""",
                flow,
            )
            if result:
                # 验证 token 质量
                _validate_token(result, flow, attempt)
                return result
            print(f"[Playwright Sentinel] {flow}: SDK 返回空值 (attempt {attempt})")
        except Exception as e:
            print(f"[Playwright Sentinel] {flow} 失败 (attempt {attempt}/{MAX_RETRIES}): {e}")
            _cleanup_thread_page()  # 强制下次重建 page

    return None


def generate_sentinel_tokens_batch(flows, proxy=None, user_agent=None):
    """
    批量生成多个 flow 的 sentinel token（复用同一个页面）。

    返回: dict[flow_name -> token_json_string]
    """
    results = {}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ctx, page = _get_or_create_page(proxy=proxy, user_agent=user_agent)
            raw = page.evaluate(
                """async (flows) => {
                    if (!window.SentinelSDK) throw new Error('SentinelSDK not loaded');
                    const out = {};
                    for (const flow of flows) {
                        try {
                            await window.SentinelSDK.init(flow);
                            const tok = await window.SentinelSDK.token(flow);
                            out[flow] = tok || null;
                        } catch (e) {
                            out[flow] = null;
                        }
                    }
                    return out;
                }""",
                flows,
            )
            for flow, tok in (raw or {}).items():
                if tok:
                    results[flow] = tok

            if results:
                return results

            print(f"[Playwright Sentinel] batch 全部返回空 (attempt {attempt})")
        except Exception as e:
            print(f"[Playwright Sentinel] batch 失败 (attempt {attempt}/{MAX_RETRIES}): {e}")
            _cleanup_thread_page()

    return results


def _validate_token(token_str, flow, attempt):
    """验证 Playwright 返回的 token 质量，打印关键字段信息"""
    try:
        if isinstance(token_str, str):
            data = json.loads(token_str)
        elif isinstance(token_str, dict):
            data = token_str
        else:
            print(f"[Playwright Sentinel] {flow} token 类型异常: {type(token_str)}")
            return

        p_len = len(data.get("p", "") or "")
        t_len = len(data.get("t", "") or "")
        c_len = len(data.get("c", "") or "")
        has_turnstile = t_len > 10
        print(f"[Playwright Sentinel] {flow} token (attempt {attempt}): "
              f"p={p_len}字符, t={t_len}字符{'✓' if has_turnstile else '✗ (无Turnstile!)'}, "
              f"c={c_len}字符, flow={data.get('flow', '?')}")
        if not has_turnstile:
            print(f"[Playwright Sentinel] ⚠️  Turnstile 为空，token 可能被服务端拒绝")
    except Exception as e:
        # token 可能不是 JSON 格式（SDK 直接返回字符串 token）
        print(f"[Playwright Sentinel] {flow} token 非 JSON: {str(token_str)[:100]}...")


def cleanup_browser():
    """关闭全局浏览器（在程序退出或任务结束时调用）"""
    _cleanup_thread_page()
    with _browser_lock:
        _close_browser_unlocked()


def is_playwright_available():
    """检查 playwright 是否已安装且 chromium 可用"""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False
