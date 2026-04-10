"""
ChatGPT 批量自动注册工具 (纯协议版) - DuckMail 临时邮箱 + Codex OAuth
依赖: pip install curl_cffi
功能: 纯协议实现注册 → Codex OAuth 全流程，无需浏览器
"""

import os
import re
import uuid
import json
import random
import string
import time
import sys
import threading
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import traceback
import secrets
import hashlib
import base64
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urlencode

from curl_cffi import requests as curl_requests
from sentinel_sdk_version import get_sentinel_sdk_version, get_sentinel_frame_url, get_sentinel_sdk_url

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ================= 加载配置 =================
def _load_config():
    """从 config.json 加载配置，环境变量优先级更高"""
    config = {
        "total_accounts": 4,
        "mail_provider": "duckmail",
        "duckmail_api_base": "",
        "duckmail_domain": "",
        "duckmail_bearer": "",
        "cf_mail_api_base": "",
        "cf_mail_domain": "",
        "cf_mail_admin_password": "",
        "cf_mail_jwt_secret": "",
        "yyds_mail_api_base": "https://maliapi.215.im/v1",
        "yyds_mail_api_key": "",
        "yyds_mail_domain": "",
        "yyds_mail_domains": [],
        "proxy": "",
        "output_file": "registered_accounts.txt",
        "csv_file": "registered_accounts.csv",
        "enable_oauth": True,
        "oauth_required": True,
        "oauth_issuer": "https://auth.openai.com",
        "oauth_client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "oauth_redirect_uri": "http://localhost:1455/auth/callback",
        "ak_file": "ak.txt",
        "rk_file": "rk.txt",
        "token_json_dir": "codex_tokens",
        "upload_api_url": "",
        "upload_api_token": "",
    }

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"⚠️ 加载 config.json 失败: {e}")

    config["mail_provider"] = os.environ.get("MAIL_PROVIDER", config["mail_provider"])
    config["duckmail_api_base"] = os.environ.get("DUCKMAIL_API_BASE", config["duckmail_api_base"])
    config["duckmail_bearer"] = os.environ.get("DUCKMAIL_BEARER", config["duckmail_bearer"])
    config["duckmail_domain"] = os.environ.get("DUCKMAIL_DOMAIN", config["duckmail_domain"])
    config["cf_mail_api_base"] = os.environ.get("CF_MAIL_API_BASE", config["cf_mail_api_base"])
    config["cf_mail_admin_password"] = os.environ.get("CF_MAIL_ADMIN_PASSWORD", config["cf_mail_admin_password"])
    config["cf_mail_jwt_secret"] = os.environ.get("CF_MAIL_JWT_SECRET", config["cf_mail_jwt_secret"])
    config["cf_mail_domain"] = os.environ.get("CF_MAIL_DOMAIN", config["cf_mail_domain"])
    config["yyds_mail_api_base"] = os.environ.get("YYDS_MAIL_API_BASE", config["yyds_mail_api_base"])
    config["yyds_mail_api_key"] = os.environ.get("YYDS_MAIL_API_KEY", config["yyds_mail_api_key"])
    config["yyds_mail_domain"] = os.environ.get("YYDS_MAIL_DOMAIN", config["yyds_mail_domain"])
    config["mailapi_icu_email"] = os.environ.get("MAILAPI_ICU_EMAIL", config.get("mailapi_icu_email", ""))
    config["mailapi_icu_order_no"] = os.environ.get("MAILAPI_ICU_ORDER_NO", config.get("mailapi_icu_order_no", ""))
    config["mailapi_icu_bulk"] = config.get("mailapi_icu_bulk", [])
    config["proxy"] = os.environ.get("PROXY", config["proxy"])
    config["total_accounts"] = int(os.environ.get("TOTAL_ACCOUNTS", config["total_accounts"]))
    config["enable_oauth"] = os.environ.get("ENABLE_OAUTH", config["enable_oauth"])
    config["oauth_required"] = os.environ.get("OAUTH_REQUIRED", config["oauth_required"])
    config["oauth_issuer"] = os.environ.get("OAUTH_ISSUER", config["oauth_issuer"])
    config["oauth_client_id"] = os.environ.get("OAUTH_CLIENT_ID", config["oauth_client_id"])
    config["oauth_redirect_uri"] = os.environ.get("OAUTH_REDIRECT_URI", config["oauth_redirect_uri"])
    config["ak_file"] = os.environ.get("AK_FILE", config["ak_file"])
    config["rk_file"] = os.environ.get("RK_FILE", config["rk_file"])
    config["token_json_dir"] = os.environ.get("TOKEN_JSON_DIR", config["token_json_dir"])
    config["upload_api_url"] = os.environ.get("UPLOAD_API_URL", config["upload_api_url"])
    config["upload_api_token"] = os.environ.get("UPLOAD_API_TOKEN", config["upload_api_token"])

    return config


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


_CONFIG = _load_config()
MAIL_PROVIDER = _CONFIG.get("mail_provider", "duckmail").strip().lower()
DUCKMAIL_API_BASE = _CONFIG["duckmail_api_base"]
DUCKMAIL_DOMAIN = _CONFIG.get("duckmail_domain", "duckmail.sbs")
DUCKMAIL_BEARER = _CONFIG["duckmail_bearer"]
CF_MAIL_API_BASE = _CONFIG.get("cf_mail_api_base", "")
# 支持中英文逗号分隔的多域名，统一转为列表；向后兼容保留单值 CF_MAIL_DOMAIN
_raw_cf_domain = _CONFIG.get("cf_mail_domain", "")
CF_MAIL_DOMAINS: list = [
    d.strip()
    for d in _raw_cf_domain.replace("，", ",").split(",")
    if d.strip()
]
CF_MAIL_DOMAIN = CF_MAIL_DOMAINS[0] if CF_MAIL_DOMAINS else ""
CF_MAIL_ADMIN_PASSWORD = _CONFIG.get("cf_mail_admin_password", "")
CF_MAIL_JWT_SECRET = _CONFIG.get("cf_mail_jwt_secret", "")
# YYDS Mail 配置
YYDS_MAIL_API_BASE = _CONFIG.get("yyds_mail_api_base", "https://maliapi.215.im/v1").rstrip("/")
YYDS_MAIL_API_KEY = _CONFIG.get("yyds_mail_api_key", "")
_raw_yyds_domain = _CONFIG.get("yyds_mail_domain", "")
_raw_yyds_domains = _CONFIG.get("yyds_mail_domains", [])
# yyds_mail 支持 domains 列表多域名轮询；domain 单域名作为兜底
if isinstance(_raw_yyds_domains, list) and _raw_yyds_domains:
    YYDS_MAIL_DOMAINS: list = [d.strip() for d in _raw_yyds_domains if isinstance(d, str) and d.strip()]
elif _raw_yyds_domain:
    YYDS_MAIL_DOMAINS = [d.strip() for d in _raw_yyds_domain.replace("，", ",").split(",") if d.strip()]
else:
    YYDS_MAIL_DOMAINS = []
YYDS_MAIL_DOMAIN = YYDS_MAIL_DOMAINS[0] if YYDS_MAIL_DOMAINS else ""
# MailAPI.ICU 配置
MAILAPI_ICU_EMAIL = _CONFIG.get("mailapi_icu_email", "").strip()
MAILAPI_ICU_ORDER_NO = _CONFIG.get("mailapi_icu_order_no", "").strip()
MAILAPI_ICU_API_BASE = "https://mailapi.icu"
# 批量导入池：从 API URL 中自动提取 orderNo
MAILAPI_ICU_BULK: list = []
_raw_bulk = _CONFIG.get("mailapi_icu_bulk", [])
if isinstance(_raw_bulk, list):
    for item in _raw_bulk:
        if not isinstance(item, dict):
            continue
        email = (item.get("email") or "").strip()
        api_url = (item.get("api_url") or "").strip()
        if email and api_url:
            # 从 URL 中提取 orderNo 参数
            order_no = ""
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(api_url)
                qs = parse_qs(parsed.query)
                order_no = qs.get("orderNo", [""])[0]
            except Exception:
                pass
            MAILAPI_ICU_BULK.append({"email": email, "order_no": order_no, "api_url": api_url})
MAILAPI_ICU_BULK_INDEX = 0  # 轮换索引
MAILAPI_ICU_BULK_LOCK = threading.Lock()  # 线程安全锁

DEFAULT_TOTAL_ACCOUNTS = _CONFIG["total_accounts"]
DEFAULT_PROXY = _CONFIG["proxy"]
DEFAULT_OUTPUT_FILE = _CONFIG["output_file"]
CSV_FILE = _CONFIG.get("csv_file", "registered_accounts.csv")
ENABLE_OAUTH = _as_bool(_CONFIG.get("enable_oauth", True))
OAUTH_REQUIRED = _as_bool(_CONFIG.get("oauth_required", True))
OAUTH_ISSUER = _CONFIG["oauth_issuer"].rstrip("/")
OAUTH_CLIENT_ID = _CONFIG["oauth_client_id"]
OAUTH_REDIRECT_URI = _CONFIG["oauth_redirect_uri"]
AK_FILE = _CONFIG["ak_file"]
RK_FILE = _CONFIG["rk_file"]
TOKEN_JSON_DIR = _CONFIG["token_json_dir"]
UPLOAD_API_URL = _CONFIG["upload_api_url"]
UPLOAD_API_TOKEN = _CONFIG["upload_api_token"]

if MAIL_PROVIDER == "cloudflare":
    if not CF_MAIL_ADMIN_PASSWORD and not CF_MAIL_JWT_SECRET:
        print("⚠️ 警告: 邮箱提供商为 CloudflareMail 但未设置 cf_mail_admin_password 或 cf_mail_jwt_secret")
elif MAIL_PROVIDER == "yyds_mail":
    if not YYDS_MAIL_API_KEY:
        print("⚠️ 警告: 邮箱提供商为 YYDS Mail 但未设置 yyds_mail_api_key")
elif MAIL_PROVIDER == "mailapi_icu":
    if (not MAILAPI_ICU_EMAIL or not MAILAPI_ICU_ORDER_NO) and not MAILAPI_ICU_BULK:
        print("⚠️ 警告: 邮箱提供商为 MailAPI.ICU 但未设置单个邮箱/订单号，且批量池为空")
else:
    if not DUCKMAIL_BEARER:
        print("⚠️ 警告: 邮箱提供商为 DuckMail 但未设置 duckmail_bearer")

# 全局线程锁
_print_lock = threading.Lock()
_file_lock = threading.Lock()


# ================= Chrome 指纹配置 =================
_CHROME_PROFILES = [
    {
        "major": 131, "impersonate": "chrome131",
        "build": 6778, "patch_range": (69, 205),
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    {
        "major": 133, "impersonate": "chrome133a",
        "build": 6943, "patch_range": (33, 153),
        "sec_ch_ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    },
    {
        "major": 136, "impersonate": "chrome136",
        "build": 7103, "patch_range": (48, 175),
        "sec_ch_ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    },
]


def _random_chrome_version():
    profile = random.choice(_CHROME_PROFILES)
    major = profile["major"]
    build = profile["build"]
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{major}.0.{build}.{patch}"
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    return profile["impersonate"], major, full_ver, ua, profile["sec_ch_ua"]


def _random_delay(low=0.3, high=1.0):
    time.sleep(random.uniform(low, high))


def _make_trace_headers():
    trace_id = str(random.getrandbits(64))
    parent_id = str(random.getrandbits(64))
    trace_hex = format(int(trace_id), "016x")
    parent_hex = format(int(parent_id), "016x")
    return {
        "traceparent": f"00-0000000000000000{trace_hex}-{parent_hex}-01",
        "tracestate": "dd=s:1;o:rum",
        "x-datadog-origin": "rum", "x-datadog-sampling-priority": "1",
        "x-datadog-trace-id": trace_id, "x-datadog-parent-id": parent_id,
    }


def _generate_pkce():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _generate_password(length=14):
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%&*"
    pwd = [random.choice(lower), random.choice(upper),
           random.choice(digits), random.choice(special)]
    all_chars = lower + upper + digits + special
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)


def _random_name():
    first_names = [
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
        "Lucas", "Mia", "Mason", "Isabella", "Logan", "Charlotte", "Alexander",
        "Amelia", "Benjamin", "Harper", "William", "Evelyn", "Henry", "Abigail",
        "Sebastian", "Emily", "Jack", "Elizabeth", "Michael", "Robert", "David",
        "Joseph", "Thomas", "Christopher", "Daniel", "Matthew", "Anthony",
        "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Susan", "Jessica",
        "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
        "Ashley", "Kimberly", "Donna", "Michelle", "Dorothy", "Carol",
        "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon",
    ]
    last_names = [
        "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor",
        "Clark", "Hall", "Young", "Anderson", "Thomas", "Jackson", "White",
        "Harris", "Martin", "Thompson", "Garcia", "Robinson", "Lewis",
        "Walker", "Allen", "King", "Wright", "Scott", "Green", "Adams",
        "Nelson", "Baker", "Rivera", "Campbell", "Mitchell", "Carter",
        "Roberts", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def _random_birthdate():
    y = random.randint(1980, 2002)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}"


# ================= Sentinel Token (PoW) =================

class SentinelTokenGenerator:
    """纯 Python 版本 sentinel token 生成器（PoW）"""

    MAX_ATTEMPTS = 500000
    ERROR_PREFIX = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"

    def __init__(self, device_id=None, user_agent=None):
        self.device_id = device_id or str(uuid.uuid4())
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        )
        self.requirements_seed = str(random.random())
        self.sid = str(uuid.uuid4())

    @staticmethod
    def _fnv1a_32(text: str):
        h = 2166136261
        for ch in text:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        h ^= (h >> 16)
        h = (h * 2246822507) & 0xFFFFFFFF
        h ^= (h >> 13)
        h = (h * 3266489909) & 0xFFFFFFFF
        h ^= (h >> 16)
        h &= 0xFFFFFFFF
        return format(h, "08x")

    def _get_config(self):
        now_str = time.strftime(
            "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
            time.gmtime(),
        )
        perf_now = random.uniform(1000, 50000)
        time_origin = time.time() * 1000 - perf_now
        nav_prop = random.choice([
            "vendorSub", "productSub", "vendor", "maxTouchPoints",
            "scheduling", "userActivation", "doNotTrack", "geolocation",
            "connection", "plugins", "mimeTypes", "pdfViewerEnabled",
            "webkitTemporaryStorage", "webkitPersistentStorage",
            "hardwareConcurrency", "cookieEnabled", "credentials",
            "mediaDevices", "permissions", "locks", "ink",
        ])
        nav_val = f"{nav_prop}-undefined"

        # 第一个元素：screen.width * screen.height 的 murmur-like hash（整数，非分辨率字符串）
        screen_hash = random.choice([4880, 4096, 5120, 3840, 4480])
        hw_concurrency = random.choice([4, 8, 12, 16])

        return [
            screen_hash, now_str, 4294705152, random.random(),
            self.user_agent,
            get_sentinel_sdk_url(),
            None, None, "en-US", "en-US,en", random.random(), nav_val,
            random.choice(["location", "implementation", "URL", "documentURI", "compatMode"]),
            random.choice(["Object", "Function", "Array", "Number", "parseFloat", "undefined"]),
            perf_now, self.sid, "",
            hw_concurrency, time_origin,
            0, 0, 0, 0, 0, 0, 0,
        ]

    @staticmethod
    def _base64_encode(data):
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def _run_check(self, start_time, seed, difficulty, config, nonce):
        config[3] = nonce
        config[9] = round((time.time() - start_time) * 1000)
        data = self._base64_encode(config)
        hash_hex = self._fnv1a_32(seed + data)
        diff_len = len(difficulty)
        if hash_hex[:diff_len] <= difficulty:
            return data + "~S"
        return None

    def generate_token(self, seed=None, difficulty=None):
        seed = seed if seed is not None else self.requirements_seed
        difficulty = str(difficulty or "0")
        start_time = time.time()
        config = self._get_config()
        for i in range(self.MAX_ATTEMPTS):
            result = self._run_check(start_time, seed, difficulty, config, i)
            if result:
                return "gAAAAAB" + result
        return "gAAAAAB" + self.ERROR_PREFIX + self._base64_encode(str(None))

    def generate_requirements_token(self):
        config = self._get_config()
        config[3] = 1
        config[9] = round(random.uniform(5, 50))
        data = self._base64_encode(config)
        return "gAAAAAC" + data


def fetch_sentinel_challenge(session, device_id, flow="authorize_continue", user_agent=None,
                             sec_ch_ua=None, impersonate=None):
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)
    req_body = {"p": generator.generate_requirements_token(), "id": device_id, "flow": flow}
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "Referer": get_sentinel_frame_url(),
        "Origin": "https://sentinel.openai.com",
        "User-Agent": user_agent or "Mozilla/5.0",
        "sec-ch-ua": sec_ch_ua or '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
    }
    kwargs = {"data": json.dumps(req_body), "headers": headers, "timeout": 20}
    if impersonate:
        kwargs["impersonate"] = impersonate
    try:
        resp = session.post("https://sentinel.openai.com/backend-api/sentinel/req", **kwargs)
    except Exception as e:
        print(f"[Sentinel] fetch_sentinel_challenge 请求异常: {e}")
        return None
    if resp.status_code != 200:
        print(f"[Sentinel] fetch_sentinel_challenge 返回 HTTP {resp.status_code}, body: {resp.text[:500]}")
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _build_sentinel_token_http(session, device_id, flow, user_agent=None,
                               sec_ch_ua=None, impersonate=None):
    """纯 HTTP 方式构建 sentinel token（无 Turnstile，t 字段为空）"""
    challenge = fetch_sentinel_challenge(session, device_id, flow=flow, user_agent=user_agent,
                                         sec_ch_ua=sec_ch_ua, impersonate=impersonate)
    if not challenge:
        return None
    c_value = challenge.get("token", "")
    if not c_value:
        return None
    pow_data = challenge.get("proofofwork") or {}
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)
    if pow_data.get("required") and pow_data.get("seed"):
        p_value = generator.generate_token(seed=pow_data.get("seed"), difficulty=pow_data.get("difficulty", "0"))
    else:
        p_value = generator.generate_requirements_token()
    print(f"[Sentinel] 纯 HTTP 方式成功获取 {flow} token (无 Turnstile)")
    return json.dumps({"p": p_value, "t": "", "c": c_value, "id": device_id, "flow": flow}, separators=(",", ":"))


def _build_sentinel_token_playwright(flow, proxy=None, user_agent=None):
    """Playwright 方式构建 sentinel token（含完整 Turnstile）"""
    try:
        from playwright_sentinel import generate_sentinel_token_playwright, is_playwright_available
        if not is_playwright_available():
            print("[Sentinel] Playwright 未安装，跳过")
            return None
        token = generate_sentinel_token_playwright(flow, proxy=proxy, user_agent=user_agent)
        if token:
            print(f"[Sentinel] Playwright 方式成功获取 {flow} token (含 Turnstile)")
        else:
            print(f"[Sentinel] Playwright 方式未能获取 {flow} token")
        return token
    except Exception as e:
        print(f"[Sentinel] Playwright 异常: {e}")
        return None


def build_sentinel_token(session, device_id, flow="authorize_continue", user_agent=None,
                         sec_ch_ua=None, impersonate=None, proxy=None, require_turnstile=False):
    """构建 sentinel token

    Args:
        require_turnstile: 如果为 True，优先使用 Playwright（因为需要 Turnstile t 字段）。
                          register / create_account 等写操作需设为 True。
    """
    if require_turnstile:
        # 写操作（register、create_account）需要 Turnstile — Playwright 优先
        token = _build_sentinel_token_playwright(flow, proxy=proxy, user_agent=user_agent)
        if token:
            return token
        # Playwright 不可用时回退 HTTP（可能被服务端拒绝，但至少能试）
        print(f"[Sentinel] Playwright 不可用，回退纯 HTTP (flow={flow})")
        return _build_sentinel_token_http(session, device_id, flow, user_agent, sec_ch_ua, impersonate)
    else:
        # 读操作 — 纯 HTTP 优先（快），失败再 Playwright
        token = _build_sentinel_token_http(session, device_id, flow, user_agent, sec_ch_ua, impersonate)
        if token:
            return token
        print(f"[Sentinel] 纯 HTTP 失败，尝试 Playwright 回退 ({flow})...")
        return _build_sentinel_token_playwright(flow, proxy=proxy, user_agent=user_agent)


def _extract_code_from_url(url: str):
    if not url or "code=" not in url:
        return None
    try:
        return parse_qs(urlparse(url).query).get("code", [None])[0]
    except Exception:
        return None


def _decode_jwt_payload(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


# ================= Token 保存与上传 =================
def _build_default_model_mapping() -> dict:
    return {
        "gpt-3.5-turbo": "gpt-3.5-turbo",
        "gpt-3.5-turbo-0125": "gpt-3.5-turbo-0125",
        "gpt-3.5-turbo-1106": "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-16k": "gpt-3.5-turbo-16k",
        "gpt-4": "gpt-4",
        "gpt-4-turbo": "gpt-4-turbo",
        "gpt-4-turbo-preview": "gpt-4-turbo-preview",
        "gpt-4o": "gpt-4o",
        "gpt-4o-2024-08-06": "gpt-4o-2024-08-06",
        "gpt-4o-2024-11-20": "gpt-4o-2024-11-20",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4o-mini-2024-07-18": "gpt-4o-mini-2024-07-18",
        "gpt-4.5-preview": "gpt-4.5-preview",
        "gpt-4.1": "gpt-4.1",
        "gpt-4.1-mini": "gpt-4.1-mini",
        "gpt-4.1-nano": "gpt-4.1-nano",
        "o1": "o1",
        "o1-preview": "o1-preview",
        "o1-mini": "o1-mini",
        "o1-pro": "o1-pro",
        "o3": "o3",
        "o3-mini": "o3-mini",
        "o3-pro": "o3-pro",
        "o4-mini": "o4-mini",
        "gpt-5": "gpt-5",
        "gpt-5-2025-08-07": "gpt-5-2025-08-07",
        "gpt-5-chat": "gpt-5-chat",
        "gpt-5-chat-latest": "gpt-5-chat-latest",
        "gpt-5-codex": "gpt-5-codex",
        "gpt-5.3-codex-spark": "gpt-5.3-codex-spark",
        "gpt-5-pro": "gpt-5-pro",
        "gpt-5-pro-2025-10-06": "gpt-5-pro-2025-10-06",
        "gpt-5-mini": "gpt-5-mini",
        "gpt-5-mini-2025-08-07": "gpt-5-mini-2025-08-07",
        "gpt-5-nano": "gpt-5-nano",
        "gpt-5-nano-2025-08-07": "gpt-5-nano-2025-08-07",
        "gpt-5.1": "gpt-5.1",
        "gpt-5.1-2025-11-13": "gpt-5.1-2025-11-13",
        "gpt-5.1-chat-latest": "gpt-5.1-chat-latest",
        "gpt-5.1-codex": "gpt-5.1-codex",
        "gpt-5.1-codex-max": "gpt-5.1-codex-max",
        "gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
        "gpt-5.2": "gpt-5.2",
        "gpt-5.2-2025-12-11": "gpt-5.2-2025-12-11",
        "gpt-5.2-chat-latest": "gpt-5.2-chat-latest",
        "gpt-5.2-codex": "gpt-5.2-codex",
        "gpt-5.2-pro": "gpt-5.2-pro",
        "gpt-5.2-pro-2025-12-11": "gpt-5.2-pro-2025-12-11",
        "gpt-5.4": "gpt-5.4",
        "gpt-5.4-2026-03-05": "gpt-5.4-2026-03-05",
        "gpt-5.3-codex": "gpt-5.3-codex",
        "chatgpt-4o-latest": "chatgpt-4o-latest",
        "gpt-4o-audio-preview": "gpt-4o-audio-preview",
        "gpt-4o-realtime-preview": "gpt-4o-realtime-preview",
    }


def _build_codex_account_payload(email: str, tokens: dict) -> dict:
    """将 OAuth token 转换为 codex.csun.site /api/v1/admin/accounts 所需的 payload 格式"""
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    id_token = tokens.get("id_token", "")
    expires_in = tokens.get("expires_in", 863999)

    # 从 access_token JWT 中提取字段
    at_payload = _decode_jwt_payload(access_token) if access_token else {}
    at_auth = at_payload.get("https://api.openai.com/auth", {})
    chatgpt_account_id = at_auth.get("chatgpt_account_id", "")
    chatgpt_user_id = at_auth.get("chatgpt_user_id", "")
    exp_timestamp = at_payload.get("exp", 0)
    expires_at = exp_timestamp if isinstance(exp_timestamp, int) and exp_timestamp > 0 else int(time.time()) + expires_in

    # 从 id_token JWT 中提取 organization_id
    it_payload = _decode_jwt_payload(id_token) if id_token else {}
    it_auth = it_payload.get("https://api.openai.com/auth", {})
    organization_id = it_auth.get("organization_id", "")
    if not organization_id:
        orgs = it_auth.get("organizations", [])
        if orgs:
            organization_id = (orgs[0] or {}).get("id", "")

    return {
        "name": email,
        "notes": "",
        "platform": "openai",
        "type": "oauth",
        "credentials": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "expires_at": expires_at,
            "client_id": OAUTH_CLIENT_ID,
            "chatgpt_account_id": chatgpt_account_id,
            "chatgpt_user_id": chatgpt_user_id,
            "organization_id": organization_id,
            "model_mapping": _build_default_model_mapping(),
        },
        "extra": {
            "email": email,
            "openai_oauth_responses_websockets_v2_mode": "off",
            "openai_oauth_responses_websockets_v2_enabled": False,
        },
        "proxy_id": None,
        "concurrency": 10,
        "priority": 1,
        "rate_multiplier": 1,
        "group_ids": [2], #根据实际情况修改分组
        "expires_at": None,
        "auto_pause_on_expired": True,
    }

def _save_codex_tokens(email: str, tokens: dict):
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    id_token = tokens.get("id_token", "")

    if access_token:
        with _file_lock:
            with open(AK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{access_token}\n")

    if refresh_token:
        with _file_lock:
            with open(RK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{refresh_token}\n")

    if not access_token:
        return

    payload = _decode_jwt_payload(access_token)
    auth_info = payload.get("https://api.openai.com/auth", {})
    account_id = auth_info.get("chatgpt_account_id", "")

    exp_timestamp = payload.get("exp")
    expired_str = ""
    if isinstance(exp_timestamp, int) and exp_timestamp > 0:
        from datetime import datetime, timezone, timedelta
        exp_dt = datetime.fromtimestamp(exp_timestamp, tz=timezone(timedelta(hours=8)))
        expired_str = exp_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    from datetime import datetime, timezone, timedelta
    now = datetime.now(tz=timezone(timedelta(hours=8)))
    token_data = {
        "type": "codex", "email": email, "expired": expired_str,
        "id_token": id_token, "account_id": account_id,
        "access_token": access_token,
        "last_refresh": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "refresh_token": refresh_token, "websockets": True,
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_dir = TOKEN_JSON_DIR if os.path.isabs(TOKEN_JSON_DIR) else os.path.join(base_dir, TOKEN_JSON_DIR)
    os.makedirs(token_dir, exist_ok=True)
    token_path = os.path.join(token_dir, f"{email}.json")
    with _file_lock:
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False)

    if UPLOAD_API_URL:
        # 推送到管理平台
        _upload_token_json(token_path)


def _upload_token_json(filepath):
    """旧版上传（使用标准 requests 避免 curl_cffi TLS 问题）"""
    try:
        import requests as std_requests
        filename = os.path.basename(filepath)
        session = std_requests.Session()
        session.verify = False
        if DEFAULT_PROXY:
            session.proxies = {"http": DEFAULT_PROXY, "https": DEFAULT_PROXY}
        with open(filepath, "rb") as f:
            resp = session.post(
                UPLOAD_API_URL,
                files={"file": (filename, f, "application/json")},
                headers={"Authorization": f"Bearer {UPLOAD_API_TOKEN}"},
                timeout=30,
            )
        if resp.status_code in (200, 201):
            with _print_lock:
                print(f"  Token JSON 已上传到管理平台")
        else:
            with _print_lock:
                print(f"  上传失败: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        with _print_lock:
            print(f"  上传异常: {e}")


def refresh_one_token(token_filepath):
    """刷新单个 codex token 文件的 refresh_token

    返回值:
    - dict: 刷新成功，返回更新后的 token 数据
    - "network_error": 网络/代理异常（不能判定 token 是否失效）
    - None: 真实的认证失败（401/403 等，token 确实无效）
    """
    import requests as std_requests
    try:
        with open(token_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    rt = data.get("refresh_token", "")
    if not rt:
        # 外部导入的 token 可能没有 refresh_token，通过 access_token 过期时间判断是否存活
        exp = data.get("exp")
        if isinstance(exp, int) and exp > time.time():
            return data  # access_token 未过期，视为存活，跳过刷新
        return None

    # 构建标准 HTTP session（不使用 curl_cffi，避免 TLS 指纹问题）
    session = std_requests.Session()
    session.verify = False
    if DEFAULT_PROXY:
        session.proxies = {"http": DEFAULT_PROXY, "https": DEFAULT_PROXY}

    try:
        resp = session.post(
            f"{OAUTH_ISSUER}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": OAUTH_CLIENT_ID,
                "refresh_token": rt,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except (std_requests.exceptions.ConnectionError,
            std_requests.exceptions.ProxyError,
            std_requests.exceptions.Timeout,
            OSError) as e:
        # 网络/代理/超时异常 → 无法判定 token 真实状态，返回 network_error
        return "network_error"
    except Exception:
        # 其他未知异常也视为网络问题，安全起见不判定为 401
        return "network_error"

    if resp.status_code in (401, 403):
        # 真实的认证失败
        return None

    if resp.status_code != 200:
        # 服务端异常（5xx 等），不能确定 token 状态
        return "network_error"

    try:
        new_tokens = resp.json()
    except Exception:
        return "network_error"

    new_at = new_tokens.get("access_token", "")
    if not new_at:
        return None

    # 解析新 access_token 的过期时间
    payload = _decode_jwt_payload(new_at)
    exp_timestamp = payload.get("exp")
    expired_str = ""
    if isinstance(exp_timestamp, int) and exp_timestamp > 0:
        from datetime import datetime, timezone, timedelta
        exp_dt = datetime.fromtimestamp(exp_timestamp, tz=timezone(timedelta(hours=8)))
        expired_str = exp_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    from datetime import datetime, timezone, timedelta
    now = datetime.now(tz=timezone(timedelta(hours=8)))

    # 更新 token 数据（保留原有字段，仅更新变化的部分）
    data["access_token"] = new_at
    data["expired"] = expired_str
    data["last_refresh"] = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    if new_tokens.get("refresh_token"):
        data["refresh_token"] = new_tokens["refresh_token"]
    if new_tokens.get("id_token"):
        data["id_token"] = new_tokens["id_token"]

    # 写回文件
    try:
        with open(token_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        return None

    return data


WHAM_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
SPARK_METERED_FEATURE = "codex_bengalfox"
DEFAULT_USER_AGENT = "codex_cli_rs/0.76.0 (Debian 13.0.0; x86_64) WindowsTerminal"


def probe_usage(token_filepath, cpa_base_url="", cpa_token="", cpa_proxy="",
                auth_index="", chatgpt_account_id=""):
    """通过 CPA api-call 探测账号真实用量状态

    返回: "alive" | "401" | "quota_limited" | "error"
    - alive: 账号正常可用
    - 401: 认证失效（access_token 过期或被封）
    - quota_limited: 额度耗尽
    - error: 探测失败（网络异常等），应保留不动
    """
    # 优先通过 CPA api-call（需要 auth_index + chatgpt_account_id）
    if cpa_base_url and cpa_token and auth_index:
        return _probe_via_cpa(
            cpa_base_url, cpa_token, cpa_proxy,
            auth_index=auth_index,
            chatgpt_account_id=chatgpt_account_id,
        )

    # 无 CPA 或缺少 auth_index 时，回退：直接用 access_token 请求
    try:
        with open(token_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return "error"

    access_token = data.get("access_token", "")
    if not access_token:
        exp = data.get("exp")
        if isinstance(exp, int) and exp > time.time():
            return "alive"
        return "401"

    return _probe_direct(access_token, cpa_proxy, chatgpt_account_id)


def _probe_via_cpa(cpa_base_url, cpa_token, proxy="",
                   auth_index="", chatgpt_account_id=""):
    """通过 CPA api-call 代理请求 wham/usage（正确方式：authIndex + $TOKEN$）

    CPA 会根据 authIndex 找到对应的 token 文件，将 $TOKEN$ 替换为真实 access_token，
    然后代为请求 wham/usage。
    """
    import requests as std_requests

    if not auth_index:
        return "error"

    session = std_requests.Session()
    session.verify = False
    if proxy:
        p = proxy if "://" in proxy else f"http://{proxy}"
        session.proxies = {"http": p, "https": p}

    # 按 cpa-warden 的格式构造 payload
    header = {
        "Authorization": "Bearer $TOKEN$",
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if chatgpt_account_id:
        header["Chatgpt-Account-Id"] = chatgpt_account_id

    payload = {
        "authIndex": auth_index,
        "method": "GET",
        "url": WHAM_USAGE_URL,
        "header": header,
    }

    try:
        resp = session.post(
            f"{cpa_base_url}/v0/management/api-call",
            json=payload,
            headers={
                "Authorization": f"Bearer {cpa_token}",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except Exception:
        return "error"

    # CPA 自身返回非 200 → 探测失败
    if resp.status_code != 200:
        return "error"

    try:
        result = resp.json()
    except Exception:
        return "error"

    if not isinstance(result, dict):
        return "error"

    # 检查上游状态码
    status_code = result.get("status_code")
    if status_code is None:
        return "error"

    if status_code == 401:
        return "401"

    if status_code != 200:
        return "error"

    # 解析 body
    body = result.get("body")
    if isinstance(body, dict):
        parsed_body = body
    elif isinstance(body, str):
        try:
            parsed_body = json.loads(body)
        except Exception:
            return "error"
    elif body is None:
        parsed_body = {}
    else:
        return "error"

    return _parse_usage_response(parsed_body)


def _probe_direct(access_token, proxy="", chatgpt_account_id=""):
    """直接请求 wham/usage（需要能访问 chatgpt.com）"""
    import requests as std_requests

    session = std_requests.Session()
    session.verify = False
    if proxy:
        p = proxy if "://" in proxy else f"http://{proxy}"
        session.proxies = {"http": p, "https": p}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if chatgpt_account_id:
        headers["Chatgpt-Account-Id"] = chatgpt_account_id

    try:
        resp = session.get(WHAM_USAGE_URL, headers=headers, timeout=15)
    except Exception:
        return "error"

    if resp.status_code == 401 or resp.status_code == 403:
        return "401"
    if resp.status_code != 200:
        return "error"

    try:
        data = resp.json()
    except Exception:
        return "error"

    return _parse_usage_response(data)


def _find_spark_rate_limit(parsed_body):
    """查找 additional_rate_limits 中的 Spark (codex_bengalfox) 条目"""
    additional = parsed_body.get("additional_rate_limits")
    if not isinstance(additional, list):
        return None

    candidates = []
    for item in additional:
        if not isinstance(item, dict):
            continue
        rate_limit = item.get("rate_limit")
        if not isinstance(rate_limit, dict):
            continue
        candidates.append((item, rate_limit))

    # 优先匹配 metered_feature
    for item, rate_limit in candidates:
        feature = str(item.get("metered_feature") or "").strip().lower()
        if feature == SPARK_METERED_FEATURE:
            return rate_limit

    # 次优匹配 limit_name 含 Spark
    for item, rate_limit in candidates:
        name = str(item.get("limit_name") or "").strip().lower()
        if "spark" in name:
            return rate_limit

    return None


def _parse_usage_response(data):
    """解析 wham/usage 响应，判定 alive 或 quota_limited

    判定规则（严格对齐 cpa-warden classify_account_state）：
    - 先检查顶层 rate_limit.limit_reached
    - plan_type=pro 时优先看 Spark (codex_bengalfox) 的 limit_reached
    - 任一 limit_reached=true → quota_limited
    """
    if not isinstance(data, dict):
        return "error"

    # 解析顶层 rate_limit
    rate_limit = data.get("rate_limit")
    primary_limit_reached = None
    primary_allowed = None
    if isinstance(rate_limit, dict):
        lr = rate_limit.get("limit_reached")
        if isinstance(lr, bool):
            primary_limit_reached = lr
        al = rate_limit.get("allowed")
        if isinstance(al, bool):
            primary_allowed = al

    # 解析 Spark rate_limit
    spark_rate_limit = _find_spark_rate_limit(data)
    spark_limit_reached = None
    spark_allowed = None
    if isinstance(spark_rate_limit, dict):
        lr = spark_rate_limit.get("limit_reached")
        if isinstance(lr, bool):
            spark_limit_reached = lr
        al = spark_rate_limit.get("allowed")
        if isinstance(al, bool):
            spark_allowed = al

    # 判定逻辑（对齐 cpa-warden 的 resolve_quota_signal）
    plan_type = str(data.get("plan_type") or "").strip().lower()

    if plan_type == "pro" and spark_limit_reached is not None:
        # Pro 账号优先看 Spark
        if spark_limit_reached is True:
            return "quota_limited"
    else:
        # Free/Plus 账号看主限额
        if primary_limit_reached is True:
            return "quota_limited"

    return "alive"


# ================= CSV 保存 =================

def save_to_csv(email: str, password: str, dm_password: str = "", oauth_status: str = ""):
    import csv
    file_exists = os.path.exists(CSV_FILE)
    with _file_lock:
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["email", "password", "duckmail_password", "oauth_status", "timestamp"])
            writer.writerow([email, password, dm_password, oauth_status, time.strftime("%Y-%m-%d %H:%M:%S")])


# ================= ChatGPTRegister 核心类 =================

def _normalize_proxy(proxy):
    """统一代理地址格式，支持多种输入形式
    
    支持的输入格式:
      - http://user:pass@host:port
      - socks5://user:pass@host:port
      - http://host:port
      - socks5://host:port
      - user:pass@host:port          → 自动补 http://
      - host:port                    → 自动补 http://
      - 1.2.3.4:8080               → 自动补 http://
    
    Returns:
        str: 标准化后的代理 URL（含协议前缀），或空字符串
    """
    if not proxy:
        return ""
    
    proxy = proxy.strip()
    
    # 已经有协议前缀，直接返回
    if "://" in proxy:
        return proxy
    
    # 纯 host:port 或 user:pass@host:port 格式，默认补 http 协议
    return f"http://{proxy}"


def _parse_proxy_info(proxy):
    """解析代理地址的可读信息
    
    Returns:
        dict: {
            "scheme": "http" / "socks5" / ...,
            "hostname": "...",
            "port": "..." 或 "",
            "username": "..." 或 "",
            "has_auth": bool,
            "raw": "原始字符串",
        }
    """
    normalized = _normalize_proxy(proxy)
    if not normalized:
        return {"raw": proxy or "", "scheme": "", "hostname": "", "port": "", "has_auth": False}

    from urllib.parse import urlparse
    parsed = urlparse(normalized)
    return {
        "raw": proxy,
        "scheme": parsed.scheme or "http",
        "hostname": parsed.hostname or "",
        "port": str(parsed.port) if parsed.port else "",
        "username": parsed.username or "",
        "has_auth": bool(parsed.username),
    }


def _detect_proxy_ip_info(proxy=None):
    """检测代理出口 IP 及地区信息

    通过代理请求免费 IP 检测 API，返回格式化字符串用于日志显示。
    多个 API 依次尝试，确保至少一个可用。

    支持任意格式的代理地址（会自动标准化）。

    Args:
        proxy: 代理地址，支持以下格式:
              http(s)://user:pass@host:port
              socks5(h)://user:pass@host:port
              user:pass@host:port (自动补 http://)
              host:port (自动补 http://)

    Returns:
        str: 格式如 "203.0.113.50 | 美国 | 加利福尼亚"
             失败时返回 "检测失败: 原因说明"
    """
    # 标准化代理格式
    proxy = _normalize_proxy(proxy)
    
    # 免费 IP 检测 API 列表（按优先级排序）
    apis = [
        ("ip-api.com/json", None),           # 无需认证，支持代理透传，返回中文地区名
        ("ipinfo.io/json", None),            # 备选，返回英文地区名
        ("api.ip.sb/geoip", None),           # 备选
        ("ifconfig.me/ip", "ip_only"),       # 最简：仅返回纯 IP
    ]

    session = curl_requests.Session(impersonate="chrome131", verify=False)
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    for url, mode in apis:
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                continue

            if mode == "ip_only":
                ip = resp.text.strip()
                return f"{ip} | 地区未知"

            data = resp.json()
            ip = data.get("query") or data.get("ip") or ""
            if not ip:
                continue

            # 组装地区信息（优先中文）
            country = data.get("country") or data.get("country_name") or ""
            region = data.get("regionName") or data.get("region") or ""
            city = data.get("city") or ""

            if country or region:
                location = " | ".join(filter(None, [country, region, city]))
                return f"{ip} | {location}"

            return f"{ip}"

        except Exception as e:
            continue

    return "检测失败 (所有API超时)"


# ================= ChatGPTRegister 核心类 =================

class ChatGPTRegister:
    BASE = "https://chatgpt.com"
    AUTH = "https://auth.openai.com"

    def __init__(self, proxy: str = None, tag: str = ""):
        self.tag = tag
        self.device_id = str(uuid.uuid4())
        self.auth_session_logging_id = str(uuid.uuid4())
        self.impersonate, self.chrome_major, self.chrome_full, self.ua, self.sec_ch_ua = _random_chrome_version()

        # 标准化代理格式（支持 host:port / user:pass@host:port / socks5:// 等多种格式）
        self.proxy = _normalize_proxy(proxy)

        self.session = curl_requests.Session(impersonate=self.impersonate, verify=False)
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": random.choice([
                "en-US,en;q=0.9", "en-US,en;q=0.9,zh-CN;q=0.8",
                "en,en-US;q=0.9", "en-US,en;q=0.8",
            ]),
            "sec-ch-ua": self.sec_ch_ua, "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"', "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": f'"{self.chrome_full}"',
            "sec-ch-ua-platform-version": f'"{random.randint(10, 15)}.0.0"',
            "oai-device-id": self.device_id,
        })
        self.session.cookies.set("oai-did", self.device_id, domain=".auth.openai.com")
        self.session.cookies.set("oai-did", self.device_id, domain="auth.openai.com")
        self.sentinel_gen = SentinelTokenGenerator(device_id=self.device_id, user_agent=self.ua)
        self._callback_url = None

    def _print(self, msg):
        prefix = f"[{self.tag}] " if self.tag else ""
        with _print_lock:
            print(f"{prefix}{msg}")

    def _log(self, step, method, url, status, body=None):
        prefix = f"[{self.tag}] " if self.tag else ""
        lines = [f"\n{'='*60}", f"{prefix}[Step] {step}", f"{prefix}[{method}] {url}",
                 f"{prefix}[Status] {status}"]
        if body:
            try:
                lines.append(f"{prefix}[Response] {json.dumps(body, indent=2, ensure_ascii=False)[:1000]}")
            except Exception:
                lines.append(f"{prefix}[Response] {str(body)[:1000]}")
        lines.append(f"{'='*60}")
        with _print_lock:
            print("\n".join(lines))

    def _build_api_headers(self, referer: str, with_sentinel: bool = False):
        """统一构建 API 请求头 (对齐 OSS _build_headers)"""
        h = {
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": self.AUTH,
            "user-agent": self.ua,
            "sec-ch-ua": self.sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": referer,
            "oai-device-id": self.device_id,
        }
        h.update(_make_trace_headers())
        if with_sentinel:
            h["openai-sentinel-token"] = self.sentinel_gen.generate_token()
        return h

    # ---- DuckMail (使用标准 requests，避免 curl_cffi TLS 超时) ----

    def _create_duckmail_session(self):
        """使用标准 requests + retry 策略（与 cpa.py 保持一致）"""
        import requests as std_requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        session = std_requests.Session()
        retry_strategy = Retry(
            total=5, backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": self.ua, "Accept": "application/json", "Content-Type": "application/json",
        })
        if self.proxy:
            session.proxies = {"http": self.proxy, "https": self.proxy}
        return session

    @staticmethod
    @staticmethod
    def _generate_email_local_name():
        """生成类 DuckDuckGo 隐私邮箱风格的用户名: 单词组合 + 短数字后缀, 无连字符

        示例: quietlynx482, swiftpebble93, warmstone617
        """
        # 形容词池
        adjectives = [
            "calm", "warm", "cool", "soft", "bold", "fast", "keen", "pure",
            "wise", "dark", "mild", "deep", "fair", "pale", "slim", "tall",
            "tiny", "vast", "wild", "glad", "true", "rare", "safe", "neat",
            "kind", "lazy", "busy", "cozy", "dull", "flat", "grim", "hazy",
            "icy", "loud", "lush", "new", "old", "raw", "red", "shy",
            "sly", "tan", "wet", "dry", "fit", "hot", "low", "odd",
            "apt", "dim", "snug", "tidy", "brisk", "crisp", "fresh",
            "green", "quick", "quiet", "sharp", "smart", "still", "sweet",
            "swift", "clear", "clean", "light", "lucky", "noble", "proud",
            "ready", "royal", "sunny", "super", "vivid", "young",
        ]
        # 名词池
        nouns = [
            "fox", "elk", "owl", "bee", "ant", "jay", "ram", "yak",
            "cat", "dog", "eel", "fly", "cod", "bat", "hen", "ape",
            "oak", "elm", "ash", "bay", "fir", "ivy", "gem", "ore",
            "sky", "sun", "dew", "fog", "ice", "mud", "sea", "bay",
            "lake", "pond", "leaf", "moss", "pine", "reed", "vine",
            "wolf", "deer", "bear", "hawk", "lynx", "toad", "moth",
            "crab", "dove", "fawn", "hare", "lark", "mole", "newt",
            "ruby", "jade", "opal", "onyx", "iron", "zinc", "clay",
            "star", "moon", "rain", "snow", "wind", "dusk", "dawn",
            "peak", "vale", "glen", "cove", "mesa", "dell", "knoll",
            "stone", "creek", "brook", "ridge", "grove", "field",
            "pebble", "ember", "frost", "spark", "bloom", "cloud",
            "flame", "shade", "river", "ocean", "trail", "maple",
        ]
        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        suffix = random.randint(10, 9999)
        return f"{adj}{noun}{suffix}"

    def create_temp_email(self):
        """根据 MAIL_PROVIDER 分发到 DuckMail / CloudflareMail / YYDS Mail / MailAPI.ICU"""
        if MAIL_PROVIDER == "cloudflare":
            return self._create_temp_email_cf()
        if MAIL_PROVIDER == "yyds_mail":
            return self._create_temp_email_yyds()
        if MAIL_PROVIDER == "mailapi_icu":
            return self._create_temp_email_mailapi_icu()
        return self._create_temp_email_duckmail()

    def _create_temp_email_duckmail(self):
        if not DUCKMAIL_BEARER:
            raise Exception("DUCKMAIL_BEARER 未设置")
        api_base = DUCKMAIL_API_BASE.rstrip("/")
        session = self._create_duckmail_session()
        max_retries = 5
        
        is_worker = "workers.dev" in api_base or "temp-email" in api_base
        
        for attempt in range(max_retries):
            local_name = self._generate_email_local_name()
            email = f"{local_name}@{DUCKMAIL_DOMAIN}"
            password = _generate_password()
            
            try:
                print(f"  DuckMail 创建邮箱 (第{attempt+1}次): {email}")
                if is_worker:
                    payload = {
                        "admin_password": DUCKMAIL_BEARER,
                        "name": local_name,
                        "domain": DUCKMAIL_DOMAIN
                    }
                    res = session.post(f"{api_base}/new_address", json=payload, timeout=120)
                    if res.status_code == 200:
                        result = res.json()
                        if result.get("jwt"):
                            print(f"  ✅ 邮箱创建成功: {result['address']}")
                            return result["address"], password, result["jwt"]
                        raise Exception(f"Worker获取邮件 Token 失败: {res.text}")
                    elif res.status_code == 400 and "already exists" in res.text:
                        print("  ⚠️ 地址碰撞，换名重试...")
                        continue
                    else:
                        raise Exception(f"Worker创建邮箱失败: {res.status_code} - {res.text[:200]}")
                else:
                    headers = {"Authorization": f"Bearer {DUCKMAIL_BEARER}"}
                    res = session.post(f"{api_base}/accounts", json={"address": email, "password": password},
                                       headers=headers, timeout=120)
                    if res.status_code in [200, 201]:
                        result = res.json()
                        if result.get("address"):
                            print(f"  ✅ 邮箱创建成功: {result['address']}")
                            time.sleep(0.5)
                            token_res = session.post(f"{api_base}/token",
                                                     json={"address": email, "password": password},
                                                     headers=headers, timeout=120)
                            if token_res.status_code == 200:
                                mail_token = token_res.json().get("token")
                                if mail_token:
                                    print("  ✅ DuckMail token 获取成功")
                                    return email, password, mail_token
                            raise Exception(f"获取邮件 Token 失败: {token_res.status_code}")
                    elif res.status_code == 422 and "already exists" in res.text:
                        print("  ⚠️ 地址碰撞，换名重试...")
                        continue
                    else:
                        raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")
            except Exception as e:
                if "already exists" in str(e):
                    continue
                raise Exception(f"DuckMail/Worker 创建邮箱失败: {e}")
        raise Exception("DuckMail 创建邮箱失败: 超过最大重试次数")

    # ---- CloudflareMail ----

    def _create_temp_email_cf(self):
        auth_key = CF_MAIL_ADMIN_PASSWORD or CF_MAIL_JWT_SECRET
        if not auth_key:
            raise Exception("cf_mail_admin_password 未设置")
        api_base = CF_MAIL_API_BASE.rstrip("/")
        session = self._create_duckmail_session()
        max_retries = 5

        for attempt in range(max_retries):
            name = self._generate_email_local_name()
            password = _generate_password()
            # 多域名时随机选择，单域名退化为原行为
            domain = random.choice(CF_MAIL_DOMAINS) if CF_MAIL_DOMAINS else CF_MAIL_DOMAIN
            address = f"{name}@{domain}"

            try:
                print(f"  CloudflareMail 创建邮箱 (第{attempt+1}次)...")
                payload = {"enablePrefix": False, "name": name, "domain": domain}
                res = session.post(
                    f"{api_base}/admin/new_address",
                    json=payload,
                    headers={"x-admin-auth": auth_key},
                    timeout=120,
                )
                if res.status_code == 200:
                    result = res.json()
                    jwt_token = result.get("jwt")
                    actual_address = result.get("address", address)
                    if jwt_token:
                        print(f"  ✅ 邮箱创建成功: {actual_address}")
                        return actual_address, password, jwt_token
                    raise Exception(f"创建邮箱未返回 JWT: {res.text[:200]}")
                elif res.status_code == 400 and "already exists" in res.text:
                    print("  ⚠️ 地址碰撞，换名重试...")
                    continue
                else:
                    raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")
            except Exception as e:
                if "already exists" in str(e):
                    continue
                raise Exception(f"CloudflareMail 创建邮箱失败: {e}")
        raise Exception("CloudflareMail 创建邮箱失败: 超过最大重试次数")

    def _delete_temp_email_cf(self, mail_token: str):
        """通过用户 JWT 调用 DELETE /api/delete_address 删除临时邮箱，失败静默"""
        try:
            api_base = CF_MAIL_API_BASE.rstrip("/")
            session = self._create_duckmail_session()
            res = session.delete(
                f"{api_base}/api/delete_address",
                headers={"Authorization": f"Bearer {mail_token}"},
                timeout=15,
            )
            if res.status_code == 200:
                self._print("🗑️ 临时邮箱已删除")
            else:
                self._print(f"⚠️ 删除临时邮箱失败: {res.status_code}")
        except Exception as e:
            self._print(f"⚠️ 删除临时邮箱异常: {e}")

    def _fetch_emails_cf(self, mail_token: str):
        try:
            api_base = CF_MAIL_API_BASE.rstrip("/")
            session = self._create_duckmail_session()
            res = session.get(
                f"{api_base}/api/mails",
                params={"limit": 20, "offset": 0},
                headers={"Authorization": f"Bearer {mail_token}"},
                timeout=120,
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict) and "results" in data:
                    return data.get("results", [])
                return data if isinstance(data, list) else []
            else:
                print(f"  [DEBUG] CF fetch emails failed: {res.status_code} {res.text[:100]}")
            return []
        except Exception as e:
            print(f"  [DEBUG] Exception in _fetch_emails_cf: {e}")
            return []

    def _fetch_email_detail_cf(self, mail_token: str, msg_id: str):
        try:
            api_base = CF_MAIL_API_BASE.rstrip("/")
            session = self._create_duckmail_session()
            if isinstance(msg_id, str) and msg_id.startswith("/messages/"):
                msg_id = msg_id.split("/")[-1]
            res = session.get(
                f"{api_base}/api/mails/{msg_id}",
                headers={"Authorization": f"Bearer {mail_token}"},
                timeout=120,
            )
            if res.status_code == 200:
                data = res.json()
                html_val = data.get("html", "")
                text_val = data.get("text", "")
                data["html"] = html_val if html_val else text_val
                return data
        except Exception:
            pass
        return None

    def _fetch_emails_duckmail(self, mail_token: str):
        try:
            api_base = DUCKMAIL_API_BASE.rstrip("/")
            session = self._create_duckmail_session()
            is_worker = "workers.dev" in api_base or "temp-email" in api_base
            
            if is_worker:
                # Worker temp email usually expects Authorization Bearer header
                res = session.get(f"{api_base}/mails", params={"limit": 20, "offset": 0},
                                  headers={"Authorization": f"Bearer {mail_token}"}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict) and "results" in data:
                        msgs = data.get("results", [])
                        return msgs
                    return data if isinstance(data, list) else []
                else:
                    print(f"  [DEBUG] Fetch emails failed: {res.status_code} {res.text[:100]}")
                return []
            else:
                res = session.get(f"{api_base}/messages", params={"page": 1},
                                  headers={"Authorization": f"Bearer {mail_token}"}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict) and "hydra:member" in data:
                        msgs = data["hydra:member"]
                        if msgs:
                            print(f"  [DEBUG] Fetched {len(msgs)} messages from duckmail")
                        return msgs
                    elif isinstance(data, list):
                        return data
                    return []
                else:
                    print(f"  [DEBUG] Fetch emails failed: {res.status_code}")
                return []
        except Exception as e:
            print(f"  [DEBUG] Exception in _fetch_emails_duckmail: {e}")
            return []

    def _fetch_email_detail_duckmail(self, mail_token: str, msg_id: str):
        try:
            api_base = DUCKMAIL_API_BASE.rstrip("/")
            session = self._create_duckmail_session()
            is_worker = "workers.dev" in api_base or "temp-email" in api_base

            if is_worker:
                # msg_id might be just an integer id. The endpoint is typically /api/mails/:id
                if isinstance(msg_id, str) and msg_id.startswith("/messages/"):
                    msg_id = msg_id.split("/")[-1]
                res = session.get(f"{api_base}/mails/{msg_id}",
                                  headers={"Authorization": f"Bearer {mail_token}"}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    # normalizes html or text output
                    html_val = data.get("html", "")
                    text_val = data.get("text", "")
                    data["html"] = html_val if html_val else text_val
                    return data
            else:
                if isinstance(msg_id, str) and msg_id.startswith("/messages/"):
                    msg_id = msg_id.split("/")[-1]
                res = session.get(f"{api_base}/messages/{msg_id}",
                                  headers={"Authorization": f"Bearer {mail_token}"}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    # DuckMail API returns html as array, normalize to string
                    html_val = data.get("html")
                    if isinstance(html_val, list):
                        data["html"] = "\n".join(str(h) for h in html_val)
                    return data
        except Exception:
            pass
        return None

    # ---- YYDS Mail ----

    def _create_temp_email_yyds(self):
        if not YYDS_MAIL_API_KEY:
            raise Exception("YYDS_MAIL_API_KEY 未设置")
        api_base = YYDS_MAIL_API_BASE
        session = self._create_duckmail_session()
        max_retries = 5

        for attempt in range(max_retries):
            local_name = self._generate_email_local_name()
            # YYDS Mail 支持多域名轮询
            if YYDS_MAIL_DOMAINS:
                domain = random.choice(YYDS_MAIL_DOMAINS)
            elif YYDS_MAIL_DOMAIN:
                domain = YYDS_MAIL_DOMAIN
            else:
                domain = None

            payload = {"address": local_name}
            if domain:
                payload["domain"] = domain

            try:
                print(f"  YYDS Mail 创建邮箱 (第{attempt+1}次)...")
                headers = {"Accept": "application/json", "Content-Type": "application/json"}
                if YYDS_MAIL_API_KEY:
                    headers["X-API-Key"] = YYDS_MAIL_API_KEY
                res = session.post(
                    f"{api_base}/accounts",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                if res.status_code in (200, 201):
                    body = res.json() if res.content else {}
                    data = body.get("data") if isinstance(body, dict) else {}
                    if not isinstance(data, dict):
                        raise Exception(f"返回 data 结构无效: {res.text[:200]}")
                    email = str(data.get("address") or "").strip()
                    token = str(data.get("token") or "").strip()
                    if not email or not token:
                        raise Exception(f"address 或 token 为空: {res.text[:200]}")
                    password = _generate_password()
                    print(f"  ✅ YYDS Mail 邮箱创建成功: {email}")
                    return email, password, token
                elif res.status_code == 400 and "already exists" in res.text:
                    print("  ⚠️ 地址碰撞，换名重试...")
                    continue
                else:
                    raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")
            except Exception as e:
                if "already exists" in str(e):
                    continue
                raise Exception(f"YYDS Mail 创建邮箱失败: {e}")
        raise Exception("YYDS Mail 创建邮箱失败: 超过最大重试次数")

    def _fetch_emails_yyds(self, mail_token: str):
        try:
            api_base = YYDS_MAIL_API_BASE
            session = self._create_duckmail_session()
            res = session.get(
                f"{api_base}/messages",
                headers={"Accept": "application/json", "Authorization": f"Bearer {mail_token}"},
                timeout=120,
            )
            if res.status_code == 200:
                body = res.json() if res.content else {}
                if not isinstance(body, dict):
                    return []
                data = body.get("data")
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    messages = data.get("messages") or data.get("items") or data.get("list") or []
                    return messages if isinstance(messages, list) else []
                return body.get("messages") or []
            else:
                print(f"  [DEBUG] YYDS fetch emails failed: {res.status_code} {res.text[:100]}")
            return []
        except Exception as e:
            print(f"  [DEBUG] Exception in _fetch_emails_yyds: {e}")
            return []

    def _fetch_email_detail_yyds(self, mail_token: str, msg_id: str):
        try:
            api_base = YYDS_MAIL_API_BASE
            session = self._create_duckmail_session()
            normalized_id = str(msg_id).split("/")[-1]
            res = session.get(
                f"{api_base}/messages/{normalized_id}",
                headers={"Accept": "application/json", "Authorization": f"Bearer {mail_token}"},
                timeout=120,
            )
            if res.status_code == 200:
                body = res.json() if res.content else {}
                data = body.get("data") if isinstance(body, dict) else {}
                return data if isinstance(data, dict) else None
        except Exception:
            pass
        return None

    # ---- MailAPI.ICU (基于订单号的取件API) ----

    def _create_temp_email_mailapi_icu(self):
        """MailAPI.ICU: 使用已有邮箱 + 订单号，支持批量轮换"""
        # 优先使用批量池
        if MAILAPI_ICU_BULK:
            global MAILAPI_ICU_BULK_INDEX
            with MAILAPI_ICU_BULK_LOCK:
                idx = MAILAPI_ICU_BULK_INDEX % len(MAILAPI_ICU_BULK)
                item = MAILAPI_ICU_BULK[idx]
                MAILAPI_ICU_BULK_INDEX += 1
            email = item["email"]
            order_no = item["order_no"]
            password = _generate_password()
            print(f"  ✅ MailAPI.ICU [批量池 #{idx+1}/{len(MAILAPI_ICU_BULK)}]: {email}")
            return email, password, order_no

        # fallback 到单个配置
        if not MAILAPI_ICU_EMAIL:
            raise Exception("mailapi_icu_email 未设置，且批量池为空")
        if not MAILAPI_ICU_ORDER_NO:
            raise Exception("mailapi_icu_order_no 未设置，且批量池为空")
        password = _generate_password()
        mail_token = MAILAPI_ICU_ORDER_NO
        print(f"  ✅ MailAPI.ICU 使用固定邮箱: {MAILAPI_ICU_EMAIL}")
        return MAILAPI_ICU_EMAIL, password, mail_token

    def _fetch_emails_mailapi_icu(self, mail_token: str):
        """MailAPI.ICU: 通过 orderNo 获取邮件列表"""
        try:
            session = self._create_duckmail_session()
            res = session.get(
                f"{MAILAPI_ICU_API_BASE}/key",
                params={"orderNo": mail_token, "type": "json"},
                timeout=120,
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0 and data[0].get("error"):
                    print(f"  [DEBUG] MailAPI.ICU 返回错误: {data[0]['error']}")
                    return []
                return data if isinstance(data, list) else []
            elif res.status_code == 404 or res.status_code == 410:
                return []
            else:
                print(f"  [DEBUG] MailAPI.ICU fetch failed: {res.status_code} {res.text[:100]}")
            return []
        except Exception as e:
            print(f"  [DEBUG] Exception in _fetch_emails_mailapi_icu: {e}")
            return []

    def _fetch_email_detail_mailapi_icu(self, mail_token: str, msg_id: str):
        """MailAPI.ICU: 邮件详情直接在列表中已包含，无需额外请求"""
        return None

    def _extract_verification_code(self, email_content: str):
        if not email_content:
            return None
        patterns = [
            r"Verification code:?\s*(\d{6})", r"code is\s*(\d{6})",
            r"代码为[:：]?\s*(\d{6})", r"验证码[:：]?\s*(\d{6})",
            r">\s*(\d{6})\s*<", r"(?<![#&])\b(\d{6})\b",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, email_content, re.IGNORECASE)
            for code in matches:
                if code == "177010":
                    continue
                return code
        return None

    def _fetch_emails(self, mail_token: str):
        """根据 MAIL_PROVIDER 调用对应的 fetch"""
        if MAIL_PROVIDER == "cloudflare":
            return self._fetch_emails_cf(mail_token)
        if MAIL_PROVIDER == "yyds_mail":
            return self._fetch_emails_yyds(mail_token)
        if MAIL_PROVIDER == "mailapi_icu":
            return self._fetch_emails_mailapi_icu(mail_token)
        return self._fetch_emails_duckmail(mail_token)

    def _fetch_email_detail(self, mail_token: str, msg_id: str):
        """根据 MAIL_PROVIDER 调用对应的 detail"""
        if MAIL_PROVIDER == "cloudflare":
            return self._fetch_email_detail_cf(mail_token, msg_id)
        if MAIL_PROVIDER == "yyds_mail":
            return self._fetch_email_detail_yyds(mail_token, msg_id)
        if MAIL_PROVIDER == "mailapi_icu":
            return self._fetch_email_detail_mailapi_icu(mail_token, msg_id)
        return self._fetch_email_detail_duckmail(mail_token, msg_id)

    def wait_for_verification_email(self, mail_token: str, timeout: int = 120):
        self._print(f"[OTP] 等待验证码邮件 (最多 {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            messages = self._fetch_emails(mail_token)
            if messages and len(messages) > 0:
                first_msg = messages[0]
                print(f"  [DEBUG] Message keys: {list(first_msg.keys())}")
                msg_id = first_msg.get("id") or first_msg.get("@id") or first_msg.get("message_id")

                # First try: 直接获取 verification_code 字段（MailAPI.ICU 等）
                direct_code = first_msg.get("verification_code")
                if direct_code:
                    self._print(f"[OTP] 验证码: {direct_code}")
                    return direct_code

                # Second try: extract OTP from text/html content
                inline_content = first_msg.get("text") or first_msg.get("html") or first_msg.get("raw") or first_msg.get("source") or ""
                if inline_content:
                    code = self._extract_verification_code(inline_content)
                    if code:
                        self._print(f"[OTP] 验证码: {code}")
                        return code

                # Third try: fetch detail by msg_id
                if msg_id:
                    detail = self._fetch_email_detail(mail_token, str(msg_id))
                    if detail:
                        # detail 也可能有 verification_code
                        detail_code = detail.get("verification_code")
                        if detail_code:
                            self._print(f"[OTP] 验证码: {detail_code}")
                            return detail_code
                        content = detail.get("text") or detail.get("html") or detail.get("source") or ""
                        code = self._extract_verification_code(content)
                        if code:
                            self._print(f"[OTP] 验证码: {code}")
                            return code
            elapsed = int(time.time() - start_time)
            self._print(f"[OTP] 等待中... ({elapsed}s/{timeout}s)")
            time.sleep(3)
        self._print(f"[OTP] 超时 ({timeout}s)")
        return None

    # ---- 注册流程 ----

    def visit_homepage(self):
        url = f"{self.BASE}/"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("0. Visit homepage", "GET", url, r.status_code,
                   {"cookies_count": len(self.session.cookies)})

    def get_csrf(self) -> str:
        url = f"{self.BASE}/api/auth/csrf"
        r = self.session.get(url, headers={"Accept": "application/json", "Referer": f"{self.BASE}/"})
        if r.status_code != 200:
            raise Exception(f"CSRF 请求失败: HTTP {r.status_code}")
        try:
            data = r.json()
        except Exception:
            raise Exception(f"CSRF 响应非 JSON: HTTP {r.status_code}, body={r.text[:200]}")
        token = data.get("csrfToken", "")
        self._log("1. Get CSRF", "GET", url, r.status_code, data)
        if not token:
            raise Exception("Failed to get CSRF token")
        return token

    def signin(self, email: str, csrf: str) -> str:
        url = f"{self.BASE}/api/auth/signin/openai"
        params = {
            "prompt": "login", "ext-oai-did": self.device_id,
            "auth_session_logging_id": self.auth_session_logging_id,
            "ext-passkey-client-capabilities": "0000",
            "screen_hint": "login_or_signup", "login_hint": email,
        }
        form_data = {"callbackUrl": f"{self.BASE}/", "csrfToken": csrf, "json": "true"}
        r = self.session.post(url, params=params, data=form_data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json", "Referer": f"{self.BASE}/", "Origin": self.BASE,
        })
        data = r.json()
        authorize_url = data.get("url", "")
        self._log("2. Signin", "POST", url, r.status_code, data)
        if not authorize_url:
            raise Exception("Failed to get authorize URL")
        return authorize_url

    def authorize(self, url: str) -> str:
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.BASE}/", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        final_url = str(r.url)
        self._log("3. Authorize", "GET", url, r.status_code, {"final_url": final_url})
        return final_url

    def authorize_continue(self, email: str, screen_hint: str = "signup"):
        """新版注册 API: authorize/continue (带 Sentinel PoW)"""
        url = f"{self.AUTH}/api/accounts/authorize/continue"
        sentinel = build_sentinel_token(
            self.session, self.device_id, "authorize_continue",
            self.ua, self.sec_ch_ua, impersonate=self.impersonate,
            proxy=self.proxy)
        if not sentinel:
            raise Exception("Failed to get Sentinel token for authorize_continue")
        headers = {
            "referer": f"{self.AUTH}/create-account",
            "accept": "application/json",
            "content-type": "application/json",
            "openai-sentinel-token": sentinel,
        }
        body = {"username": {"value": email, "kind": "email"}, "screen_hint": screen_hint}
        r = self.session.post(url, headers=headers, json=body)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text[:500]}
        self._log("3b. Authorize Continue", "POST", url, r.status_code, data)
        return r.status_code, data

    def register(self, email: str, password: str):
        url = f"{self.AUTH}/api/accounts/user/register"
        headers = self._build_api_headers(f"{self.AUTH}/create-account/password", with_sentinel=False)
        # HAR 显示 register 需要完整 Turnstile，优先 Playwright
        sentinel = build_sentinel_token(
            self.session, self.device_id, "username_password_create",
            self.ua, self.sec_ch_ua, impersonate=self.impersonate,
            proxy=self.proxy, require_turnstile=True)
        if sentinel:
            headers["openai-sentinel-token"] = sentinel
        else:
            self._print("[register] sentinel 全部失败，使用本地 PoW（可能被拒绝）")
            headers["openai-sentinel-token"] = self.sentinel_gen.generate_token()
        r = self.session.post(url, json={"username": email, "password": password}, headers=headers)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text[:500]}
        self._log("4. Register", "POST", url, r.status_code, data)
        return r.status_code, data

    def send_otp(self):
        url = f"{self.AUTH}/api/accounts/email-otp/send"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.AUTH}/create-account/password", "Upgrade-Insecure-Requests": "1",
        }
        r = self.session.get(url, headers=headers, allow_redirects=True)
        try:
            data = r.json()
        except Exception:
            data = {"final_url": str(r.url), "status": r.status_code}
        self._log("5. Send OTP", "GET", url, r.status_code, data)
        return r.status_code, data

    def validate_otp(self, code: str, with_sentinel: bool = False):
        url = f"{self.AUTH}/api/accounts/email-otp/validate"
        headers = self._build_api_headers(f"{self.AUTH}/email-verification", with_sentinel=with_sentinel)
        r = self.session.post(url, json={"code": code}, headers=headers)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text[:500]}
        self._log("6. Validate OTP", "POST", url, r.status_code, data)
        return r.status_code, data

    def create_account(self, name: str, birthdate: str):
        url = f"{self.AUTH}/api/accounts/create_account"
        headers = self._build_api_headers(f"{self.AUTH}/about-you", with_sentinel=False)
        # HAR 显示 create_account 也需要完整 Turnstile，优先 Playwright
        sentinel = build_sentinel_token(
            self.session, self.device_id, "oauth_create_account",
            self.ua, self.sec_ch_ua, impersonate=self.impersonate,
            proxy=self.proxy, require_turnstile=True)
        if sentinel:
            headers["openai-sentinel-token"] = sentinel
        else:
            self._print("[create_account] sentinel 全部失败，使用本地 PoW（可能被拒绝）")
            headers["openai-sentinel-token"] = self.sentinel_gen.generate_token()
        r = self.session.post(url, json={"name": name, "birthdate": birthdate}, headers=headers)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text[:500]}
        self._log("7. Create Account", "POST", url, r.status_code, data)
        if isinstance(data, dict):
            cb = data.get("continue_url") or data.get("url") or data.get("redirect_url")
            if cb:
                self._callback_url = cb
        return r.status_code, data

    def callback(self, url: str = None):
        if not url:
            url = self._callback_url
        if not url:
            self._print("[!] No callback URL, skipping.")
            return None, None
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("8. Callback", "GET", url, r.status_code, {"final_url": str(r.url)})
        return r.status_code, {"final_url": str(r.url)}

    # ---- 注册主流程 (V3: 浏览器真实流程对齐 — HAR verified) ----

    def run_register(self, email, password, name, birthdate, mail_token):
        """注册流程 V3: 对齐浏览器真实流程 (HAR verified)
        流程: homepage → csrf → signin(login_hint) → authorize → register(PoW) → OTP → create_account(PoW)
        不再使用 authorize_continue，通过 login_hint 直达密码页。
        """
        # 保存 code_verifier 供后续 Codex OAuth token 交换
        code_verifier, code_challenge = _generate_pkce()
        self._code_verifier = code_verifier

        # 1. 访问首页，建立 session cookies
        self.visit_homepage()
        self._print("[注册] 1/7 首页访问")
        time.sleep(random.uniform(0.5, 1.5))

        # 2. 获取 CSRF token
        csrf = self.get_csrf()
        self._print("[注册] 2/7 CSRF 获取")
        time.sleep(random.uniform(0.3, 0.8))

        # 3. Signin (带 login_hint，服务端会直接返回 authorize URL 含邮箱信息)
        authorize_url = self.signin(email, csrf)
        self._print("[注册] 3/7 Signin 完成")
        time.sleep(random.uniform(0.5, 1.0))

        # 4. Follow authorize URL (302 → /create-account/password，login_hint 跳过邮箱输入)
        final_url = self.authorize(authorize_url)
        self._print(f"[注册] 4/7 Authorize 重定向 → {final_url[:80]}")
        time.sleep(random.uniform(0.5, 1.5))

        # 5. 设置密码 (带 Sentinel PoW, flow=username_password_create)
        status, data = self.register(email, password)
        if status != 200:
            raise Exception(f"设置密码失败 ({status}): {data}")
        self._print("[注册] 5/7 设置密码")
        time.sleep(random.uniform(0.5, 1.0))

        # 6. 发送 OTP + 验证
        self.send_otp()
        self._print("[注册] 6/7 发送 OTP")

        otp_code = self.wait_for_verification_email(mail_token)
        if not otp_code:
            raise Exception("未能获取验证码")
        time.sleep(random.uniform(0.5, 1.0))

        # HAR 显示 OTP 验证不需要 sentinel token
        status, data = self.validate_otp(otp_code, with_sentinel=False)
        if status != 200:
            self._print("[注册] OTP 验证失败，尝试 sentinel fallback...")
            status, data = self.validate_otp(otp_code, with_sentinel=True)
            if status != 200:
                self._print("[注册] sentinel 也失败，重新发送 OTP...")
                self.send_otp()
                time.sleep(2)
                otp_code = self.wait_for_verification_email(mail_token, timeout=60)
                if not otp_code:
                    raise Exception("重试后仍未获取验证码")
                time.sleep(1)
                status, data = self.validate_otp(otp_code, with_sentinel=True)
                if status != 200:
                    raise Exception(f"OTP 验证失败 ({status}): {data}")
        self._print("[注册] 6/7 OTP 验证成功")
        time.sleep(random.uniform(0.5, 1.0))

        # 7. 创建账号 (带 Sentinel PoW, flow=oauth_create_account)
        status, data = self.create_account(name, birthdate)
        if status != 200:
            raise Exception(f"创建账号失败 ({status}): {data}")
        self._print("[注册] 7/7 账号创建成功")

        # 提取 continue_url 供后续 OAuth token 交换
        self._registration_continue_url = ""
        if isinstance(data, dict):
            _continue_url = data.get("continue_url", "") or data.get("url", "") or ""
            _page_type = (data.get("page") or {}).get("type", "")
            self._registration_continue_url = _continue_url

            # 检测 add-phone — 尝试绕过
            if "add-phone" in _continue_url or "add-phone" in _page_type or "phone" in _page_type:
                self._print("[注册] 检测到 add-phone 要求，尝试绕过...")
                bypassed = self._try_bypass_phone(data)
                if not bypassed:
                    self._print("[注册] 绕过失败，跳过 callback")
                    return True

        time.sleep(random.uniform(0.5, 1.0))
        self.callback()
        return True

    def _try_bypass_phone(self, create_account_data):
        """尝试绕过 add-phone 步骤

        策略:
        1. 直接请求 consent URL 跳过手机验证
        2. 尝试 workspace/select 跳过
        3. 直接访问 callback URL（某些情况下 session 已足够）
        """
        continue_url = ""
        if isinstance(create_account_data, dict):
            continue_url = create_account_data.get("continue_url", "") or create_account_data.get("url", "") or ""

        # 策略 1: 直接跳到 consent 页面（跳过 phone step）
        consent_urls = [
            f"{self.AUTH}/sign-in-with-chatgpt/codex/consent",
            f"{self.AUTH}/api/accounts/authorize/consent",
        ]
        for consent_url in consent_urls:
            try:
                self._print(f"[bypass-phone] 尝试直接访问 consent: {consent_url[:60]}")
                r = self.session.get(consent_url, headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": f"{self.AUTH}/add-phone",
                    "Upgrade-Insecure-Requests": "1",
                }, allow_redirects=True, timeout=30)
                final_url = str(r.url)
                self._print(f"[bypass-phone] consent → {final_url[:80]} (status={r.status_code})")

                # 如果重定向到了 callback 或包含 code=，则成功
                if "code=" in final_url or "callback" in final_url:
                    self._callback_url = final_url
                    self._print("[bypass-phone] 成功绕过 add-phone (consent redirect)")
                    return True
            except Exception as e:
                self._print(f"[bypass-phone] consent 失败: {e}")

        # 策略 2: 提交 workspace/select 跳过
        try:
            self._print("[bypass-phone] 尝试 workspace/select...")
            r = self.session.post(f"{self.AUTH}/api/accounts/workspace/select",
                                  json={}, headers=self._build_api_headers(f"{self.AUTH}/add-phone"),
                                  timeout=30)
            self._print(f"[bypass-phone] workspace/select → {r.status_code}")
            if r.status_code == 200:
                try:
                    ws_data = r.json()
                    ws_url = ws_data.get("continue_url", "") or ws_data.get("url", "")
                    if ws_url and "code=" in ws_url:
                        self._callback_url = ws_url
                        self._print("[bypass-phone] 成功绕过 add-phone (workspace)")
                        return True
                except Exception:
                    pass
        except Exception as e:
            self._print(f"[bypass-phone] workspace 失败: {e}")

        # 策略 3: 直接重新发起 OAuth authorize（session 可能已携带足够认证信息）
        try:
            code_challenge = getattr(self, "_code_verifier", None)
            if code_challenge:
                _, new_challenge = _generate_pkce()
                self._print("[bypass-phone] 尝试重新发起 OAuth authorize...")
                oauth_params = {
                    "client_id": OAUTH_CLIENT_ID,
                    "response_type": "code",
                    "redirect_uri": OAUTH_REDIRECT_URI,
                    "scope": "openid email profile offline_access",
                    "state": secrets.token_urlsafe(16),
                    "code_challenge": new_challenge,
                    "code_challenge_method": "S256",
                    "prompt": "none",  # 静默模式，不弹登录
                }
                r = self.session.get(f"{OAUTH_ISSUER}/oauth/authorize",
                                     params=oauth_params, allow_redirects=True, timeout=30)
                final_url = str(r.url)
                self._print(f"[bypass-phone] re-authorize → {final_url[:80]}")
                if "code=" in final_url:
                    self._callback_url = final_url
                    self._print("[bypass-phone] 成功绕过 add-phone (re-authorize)")
                    return True
        except Exception as e:
            self._print(f"[bypass-phone] re-authorize 失败: {e}")

        return False

    # ---- 从注册会话直接换取 Codex OAuth Token ----

    def exchange_tokens_from_registration(self):
        """利用注册后的 auth session 发起 Codex OAuth（跳过重新登录）

        注册完成后 auth.openai.com 上已有登录态 cookies，
        直接发起 Codex 的 /oauth/authorize 应该能跳过 login+OTP，
        直达 consent/workspace（或 add-phone）。
        """
        self._print("[Token] 利用注册 session 发起 Codex OAuth...")

        # 生成新的 PKCE（Codex client_id 独立于 ChatGPT）
        code_verifier, code_challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)

        authorize_params = {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        authorize_url = f"{OAUTH_ISSUER}/oauth/authorize?{urlencode(authorize_params)}"

        # 发起 authorize，利用已有 session 应该不需要重新登录
        try:
            r = self.session.get(authorize_url, headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{self.BASE}/",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": self.ua,
            }, allow_redirects=True, timeout=30, impersonate=self.impersonate)
            final_url = str(r.url)
            self._print(f"[Token] Codex authorize → {final_url[:100]} (status={r.status_code})")
        except Exception as e:
            # 可能 redirect 到 localhost（Codex CLI 监听的），从异常中提取 code
            maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
            if maybe_localhost:
                code = _extract_code_from_url(maybe_localhost.group(1))
                if code:
                    return self._exchange_code_for_tokens(code, code_verifier)
            self._print(f"[Token] authorize 异常: {e}")
            return None

        # 检查是否直接拿到 code
        code = _extract_code_from_url(final_url)
        if code:
            return self._exchange_code_for_tokens(code, code_verifier)

        # 检查 redirect history 中是否有 code
        for hist in getattr(r, "history", []) or []:
            loc = hist.headers.get("Location", "")
            code = _extract_code_from_url(loc) or _extract_code_from_url(str(hist.url))
            if code:
                return self._exchange_code_for_tokens(code, code_verifier)

        # 如果落在了 log-in 页面，说明 session 已过期，需要回退到独立 OAuth
        if "/log-in" in final_url:
            self._print("[Token] session 已过期（落在 log-in 页），需要独立 OAuth 登录")
            return None

        # 如果落在 add-phone 页面
        if "add-phone" in final_url:
            self._print("[Token] 遇到 add-phone 要求，尝试跳过...")
            for skip_url in [f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"]:
                code = self._oauth_allow_redirect_extract_code(skip_url, referer=final_url)
                if code:
                    return self._exchange_code_for_tokens(code, code_verifier)
            self._print("[Token] add-phone 处理失败")
            return None

        # 如果落在 consent/workspace 页面 — 尝试处理
        if any(kw in final_url for kw in ["consent", "workspace", "organization"]):
            self._print(f"[Token] 尝试 consent/workspace 流程...")
            code = self._oauth_submit_workspace_and_org(final_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(final_url, referer=authorize_url)
            if code:
                return self._exchange_code_for_tokens(code, code_verifier)

        # 最终回退
        fallback_consent = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
        code = self._oauth_allow_redirect_extract_code(fallback_consent, referer=final_url)
        if code:
            return self._exchange_code_for_tokens(code, code_verifier)

        self._print(f"[Token] 注册 session 未获取到 auth code (final={final_url[:80]})")
        return None

    def _exchange_code_for_tokens(self, code, code_verifier):
        """用 auth code + code_verifier 换取 Codex OAuth token"""
        self._print("[Token] 获取到 auth code，交换 Codex Token...")
        token_resp = self.session.post(
            f"{OAUTH_ISSUER}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": self.ua},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "client_id": OAUTH_CLIENT_ID,
                "code_verifier": code_verifier,
            },
            timeout=60,
            impersonate=self.impersonate,
        )

        if token_resp.status_code != 200:
            self._print(f"[Token] token 交换失败: {token_resp.status_code}, {token_resp.text[:200]}")
            return None

        try:
            data = token_resp.json()
        except Exception:
            return None

        if not data.get("access_token"):
            return None

        self._print("[Token] Codex Token 获取成功 ✅")
        return data

    def _oauth_follow_for_code_from_consent(self, consent_url: str):
        """跟随 consent URL 的重定向链提取 auth code"""
        try:
            resp = self.session.get(
                consent_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": self.ua,
                },
                allow_redirects=False,
                timeout=30,
                impersonate=self.impersonate,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                code = _extract_code_from_url(loc)
                if code:
                    return code
                # 继续跟随
                code, _ = self._oauth_follow_for_code(loc, referer=consent_url)
                return code
            if resp.status_code == 200:
                code = _extract_code_from_url(str(resp.url))
                return code
        except Exception as e:
            maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
            if maybe_localhost:
                return _extract_code_from_url(maybe_localhost.group(1))
        return None

    # ---- OAuth helpers ----

    def _decode_oauth_session_cookie(self):
        jar = getattr(self.session.cookies, "jar", None)
        cookie_items = list(jar) if jar is not None else []
        for c in cookie_items:
            name = getattr(c, "name", "") or ""
            if "oai-client-auth-session" not in name:
                continue
            raw_val = (getattr(c, "value", "") or "").strip()
            if not raw_val:
                continue
            candidates = [raw_val]
            try:
                from urllib.parse import unquote
                decoded = unquote(raw_val)
                if decoded != raw_val:
                    candidates.append(decoded)
            except Exception:
                pass
            for val in candidates:
                try:
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    part = val.split(".")[0] if "." in val else val
                    pad = 4 - len(part) % 4
                    if pad != 4:
                        part += "=" * pad
                    raw = base64.urlsafe_b64decode(part)
                    data = json.loads(raw.decode("utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
        return None

    def _oauth_allow_redirect_extract_code(self, url: str, referer: str = None):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1", "User-Agent": self.ua,
        }
        if referer:
            headers["Referer"] = referer
        try:
            resp = self.session.get(url, headers=headers, allow_redirects=True,
                                    timeout=30, impersonate=self.impersonate)
            final_url = str(resp.url)
            code = _extract_code_from_url(final_url)
            if code:
                return code
            for r in getattr(resp, "history", []) or []:
                loc = r.headers.get("Location", "")
                code = _extract_code_from_url(loc) or _extract_code_from_url(str(r.url))
                if code:
                    return code
        except Exception as e:
            maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
            if maybe_localhost:
                code = _extract_code_from_url(maybe_localhost.group(1))
                if code:
                    return code
        return None

    def _oauth_follow_for_code(self, start_url: str, referer: str = None, max_hops: int = 16):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1", "User-Agent": self.ua,
        }
        if referer:
            headers["Referer"] = referer
        current_url = start_url
        last_url = start_url
        for hop in range(max_hops):
            try:
                resp = self.session.get(current_url, headers=headers, allow_redirects=False,
                                        timeout=30, impersonate=self.impersonate)
            except Exception as e:
                maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
                if maybe_localhost:
                    code = _extract_code_from_url(maybe_localhost.group(1))
                    if code:
                        return code, maybe_localhost.group(1)
                return None, last_url
            last_url = str(resp.url)
            code = _extract_code_from_url(last_url)
            if code:
                return code, last_url
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                if not loc:
                    return None, last_url
                if loc.startswith("/"):
                    loc = f"{OAUTH_ISSUER}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code, loc
                current_url = loc
                headers["Referer"] = last_url
                continue
            return None, last_url
        return None, last_url

    def _oauth_submit_workspace_and_org(self, consent_url: str):
        session_data = self._decode_oauth_session_cookie()
        if not session_data:
            self._print("[OAuth] 无法解码 oai-client-auth-session")
            return None
        workspaces = session_data.get("workspaces", [])
        if not workspaces:
            self._print("[OAuth] session 中没有 workspace 信息")
            return None
        workspace_id = (workspaces[0] or {}).get("id")
        if not workspace_id:
            return None

        h = {"Accept": "application/json", "Content-Type": "application/json",
             "Origin": OAUTH_ISSUER, "Referer": consent_url,
             "User-Agent": self.ua, "oai-device-id": self.device_id}
        h.update(_make_trace_headers())

        resp = self.session.post(f"{OAUTH_ISSUER}/api/accounts/workspace/select",
                                 json={"workspace_id": workspace_id}, headers=h,
                                 allow_redirects=False, timeout=30, impersonate=self.impersonate)
        self._print(f"[OAuth] workspace/select -> {resp.status_code}")

        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            if loc.startswith("/"):
                loc = f"{OAUTH_ISSUER}{loc}"
            code = _extract_code_from_url(loc)
            if code:
                return code
            code, _ = self._oauth_follow_for_code(loc, referer=consent_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(loc, referer=consent_url)
            return code

        if resp.status_code != 200:
            return None

        try:
            ws_data = resp.json()
        except Exception:
            return None

        ws_next = ws_data.get("continue_url", "")
        orgs = ws_data.get("data", {}).get("orgs", [])

        org_id = None
        project_id = None
        if orgs:
            org_id = (orgs[0] or {}).get("id")
            projects = (orgs[0] or {}).get("projects", [])
            if projects:
                project_id = (projects[0] or {}).get("id")

        if org_id:
            org_body = {"org_id": org_id}
            if project_id:
                org_body["project_id"] = project_id
            h_org = dict(h)
            if ws_next:
                h_org["Referer"] = ws_next if ws_next.startswith("http") else f"{OAUTH_ISSUER}{ws_next}"
            resp_org = self.session.post(f"{OAUTH_ISSUER}/api/accounts/organization/select",
                                         json=org_body, headers=h_org, allow_redirects=False,
                                         timeout=30, impersonate=self.impersonate)
            self._print(f"[OAuth] organization/select -> {resp_org.status_code}")
            if resp_org.status_code in (301, 302, 303, 307, 308):
                loc = resp_org.headers.get("Location", "")
                if loc.startswith("/"):
                    loc = f"{OAUTH_ISSUER}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code
                code, _ = self._oauth_follow_for_code(loc, referer=h_org.get("Referer"))
                if not code:
                    code = self._oauth_allow_redirect_extract_code(loc, referer=h_org.get("Referer"))
                return code
            if resp_org.status_code == 200:
                try:
                    org_data = resp_org.json()
                except Exception:
                    return None
                org_next = org_data.get("continue_url", "")
                if org_next:
                    if org_next.startswith("/"):
                        org_next = f"{OAUTH_ISSUER}{org_next}"
                    code, _ = self._oauth_follow_for_code(org_next, referer=h_org.get("Referer"))
                    if not code:
                        code = self._oauth_allow_redirect_extract_code(org_next, referer=h_org.get("Referer"))
                    return code

        if ws_next:
            if ws_next.startswith("/"):
                ws_next = f"{OAUTH_ISSUER}{ws_next}"
            code, _ = self._oauth_follow_for_code(ws_next, referer=consent_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(ws_next, referer=consent_url)
            return code
        return None

    # ---- Codex OAuth 纯协议 ----

    def perform_codex_oauth_login_http(self, email: str, password: str, mail_token: str = None):
        self._print("[OAuth] 开始执行 Codex OAuth 纯协议流程...")
        self.session.cookies.set("oai-did", self.device_id, domain=".auth.openai.com")
        self.session.cookies.set("oai-did", self.device_id, domain="auth.openai.com")

        code_verifier, code_challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)
        authorize_params = {
            "response_type": "code", "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI, "scope": "openid profile email offline_access",
            "code_challenge": code_challenge, "code_challenge_method": "S256", "state": state,
        }
        authorize_url = f"{OAUTH_ISSUER}/oauth/authorize?{urlencode(authorize_params)}"

        def _oauth_json_headers(referer: str):
            h = {"Accept": "application/json", "Content-Type": "application/json",
                 "Origin": OAUTH_ISSUER, "Referer": referer,
                 "User-Agent": self.ua, "oai-device-id": self.device_id}
            h.update(_make_trace_headers())
            return h

        def _bootstrap_oauth_session():
            self._print("[OAuth] 1/7 GET /oauth/authorize")
            try:
                r = self.session.get(authorize_url, headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": f"{self.BASE}/", "Upgrade-Insecure-Requests": "1", "User-Agent": self.ua,
                }, allow_redirects=True, timeout=30, impersonate=self.impersonate)
            except Exception as e:
                self._print(f"[OAuth] /oauth/authorize 异常: {e}")
                return False, ""
            final_url = str(r.url)
            self._print(f"[OAuth] /oauth/authorize -> {r.status_code}, final={final_url[:140]}")
            has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
            if not has_login:
                try:
                    r2 = self.session.get(f"{OAUTH_ISSUER}/api/oauth/oauth2/auth",
                                          headers={"Accept": "text/html", "Referer": authorize_url,
                                                   "User-Agent": self.ua},
                                          params=authorize_params, allow_redirects=True,
                                          timeout=30, impersonate=self.impersonate)
                    final_url = str(r2.url)
                except Exception:
                    pass
                has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
            return has_login, final_url

        def _post_authorize_continue(referer_url: str):
            sentinel = build_sentinel_token(self.session, self.device_id, flow="authorize_continue",
                                            user_agent=self.ua, sec_ch_ua=self.sec_ch_ua, impersonate=self.impersonate,
                                            proxy=self.proxy)
            if not sentinel:
                self._print("[OAuth] authorize_continue sentinel 失败")
                return None
            headers = _oauth_json_headers(referer_url)
            headers["openai-sentinel-token"] = sentinel
            try:
                return self.session.post(f"{OAUTH_ISSUER}/api/accounts/authorize/continue",
                                         json={"username": {"kind": "email", "value": email}},
                                         headers=headers, timeout=30, allow_redirects=False,
                                         impersonate=self.impersonate)
            except Exception as e:
                self._print(f"[OAuth] authorize/continue 异常: {e}")
                return None

        has_login_session, authorize_final_url = _bootstrap_oauth_session()
        if not authorize_final_url:
            return None

        continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"

        self._print("[OAuth] 2/7 POST /api/accounts/authorize/continue")
        resp_continue = _post_authorize_continue(continue_referer)
        if resp_continue is None:
            return None

        if resp_continue.status_code == 400 and "invalid_auth_step" in (resp_continue.text or ""):
            self._print("[OAuth] invalid_auth_step, 重新 bootstrap")
            has_login_session, authorize_final_url = _bootstrap_oauth_session()
            if not authorize_final_url:
                return None
            continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"
            resp_continue = _post_authorize_continue(continue_referer)
            if resp_continue is None:
                return None

        if resp_continue.status_code != 200:
            self._print(f"[OAuth] 邮箱提交失败: {resp_continue.text[:180]}")
            return None

        try:
            continue_data = resp_continue.json()
        except Exception:
            return None

        continue_url = continue_data.get("continue_url", "")
        page_type = (continue_data.get("page") or {}).get("type", "")

        self._print("[OAuth] 3/7 POST /api/accounts/password/verify")
        sentinel_pwd = build_sentinel_token(self.session, self.device_id, flow="password_verify",
                                            user_agent=self.ua, sec_ch_ua=self.sec_ch_ua, impersonate=self.impersonate,
                                            proxy=self.proxy)
        if not sentinel_pwd:
            return None

        headers_verify = _oauth_json_headers(f"{OAUTH_ISSUER}/log-in/password")
        headers_verify["openai-sentinel-token"] = sentinel_pwd

        try:
            resp_verify = self.session.post(f"{OAUTH_ISSUER}/api/accounts/password/verify",
                                            json={"password": password}, headers=headers_verify,
                                            timeout=30, allow_redirects=False, impersonate=self.impersonate)
        except Exception as e:
            self._print(f"[OAuth] password/verify 异常: {e}")
            return None

        if resp_verify.status_code != 200:
            self._print(f"[OAuth] 密码校验失败: {resp_verify.text[:180]}")
            return None

        try:
            verify_data = resp_verify.json()
        except Exception:
            return None

        continue_url = verify_data.get("continue_url", "") or continue_url
        page_type = (verify_data.get("page") or {}).get("type", "") or page_type

        # OTP 阶段
        need_oauth_otp = (page_type == "email_otp_verification"
                          or "email-verification" in (continue_url or "")
                          or "email-otp" in (continue_url or ""))

        if need_oauth_otp:
            self._print("[OAuth] 4/7 检测到邮箱 OTP 验证")
            if not mail_token:
                self._print("[OAuth] 需要 OTP 但未提供 mail_token")
                return None
            headers_otp = _oauth_json_headers(f"{OAUTH_ISSUER}/email-verification")
            tried_codes = set()
            otp_success = False
            otp_deadline = time.time() + 120
            while time.time() < otp_deadline and not otp_success:
                messages = self._fetch_emails(mail_token) or []
                candidate_codes = []
                for msg in messages[:12]:
                    code = None
                    # Try inline content first (like workers do)
                    inline_content = msg.get("text") or msg.get("html") or msg.get("raw") or msg.get("source") or ""
                    if inline_content:
                        code = self._extract_verification_code(inline_content)
                    
                    # Try fetching detail if inline extraction failed
                    if not code:
                        msg_id = msg.get("id") or msg.get("@id") or msg.get("message_id")
                        if msg_id:
                            detail = self._fetch_email_detail(mail_token, str(msg_id))
                            if detail:
                                content = detail.get("text") or detail.get("html") or detail.get("source") or ""
                                code = self._extract_verification_code(content)
                    
                    if code and code not in tried_codes:
                        candidate_codes.append(code)
                if not candidate_codes:
                    time.sleep(2)
                    continue
                for otp_code in candidate_codes:
                    tried_codes.add(otp_code)
                    self._print(f"[OAuth] 尝试 OTP: {otp_code}")
                    try:
                        resp_otp = self.session.post(f"{OAUTH_ISSUER}/api/accounts/email-otp/validate",
                                                     json={"code": otp_code}, headers=headers_otp,
                                                     timeout=30, allow_redirects=False, impersonate=self.impersonate)
                    except Exception:
                        continue
                    if resp_otp.status_code != 200:
                        continue
                    try:
                        otp_data = resp_otp.json()
                    except Exception:
                        continue
                    continue_url = otp_data.get("continue_url", "") or continue_url
                    page_type = (otp_data.get("page") or {}).get("type", "") or page_type
                    otp_success = True
                    break
                if not otp_success:
                    time.sleep(2)
            if not otp_success:
                self._print(f"[OAuth] OTP 验证失败")
                return None

        # ---- 处理中间步骤（add-phone / workspace / consent） ----
        self._print(f"[OAuth] OTP 后 continue_url={continue_url[:120] if continue_url else 'None'}, page_type={page_type}")

        code = None
        encountered_add_phone = ("add-phone" in (continue_url or "") or "add-phone" in page_type
                                 or page_type == "add_phone")

        # 检测 add-phone — 先尝试跳过直达 consent
        if encountered_add_phone:
            self._print("[OAuth] 检测到 add-phone 要求，尝试跳过...")
            try:
                skip_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
                r = self.session.get(skip_url, headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": continue_url or f"{OAUTH_ISSUER}/add-phone",
                    "User-Agent": self.ua,
                }, allow_redirects=True, timeout=30, impersonate=self.impersonate)
                final = str(r.url)
                self._print(f"[OAuth] 跳过 add-phone → final={final[:80]} (status={r.status_code})")
                code = _extract_code_from_url(final)
                if not code:
                    for hist in getattr(r, "history", []) or []:
                        code = _extract_code_from_url(hist.headers.get("Location", ""))
                        if code:
                            break
                if not code and "add-phone" not in final:
                    continue_url = final
                    page_type = ""
            except Exception as e:
                self._print(f"[OAuth] 跳过 add-phone 失败: {e}")

        # 处理 workspace / consent
        if not code and "add-phone" not in (continue_url or ""):
            consent_url = continue_url or f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
            if consent_url.startswith("/"):
                consent_url = f"{OAUTH_ISSUER}{consent_url}"
            self._print(f"[OAuth] 5/7 尝试 consent/workspace: {consent_url[-60:]}")
            code = self._oauth_submit_workspace_and_org(consent_url)
            if not code:
                code, _ = self._oauth_follow_for_code(consent_url, referer=f"{OAUTH_ISSUER}/log-in/password")
            if not code:
                code = self._oauth_allow_redirect_extract_code(consent_url, referer=f"{OAUTH_ISSUER}/log-in/password")

        # 所有跳过尝试都失败 + 最初遇到了 add-phone → 无法继续
        if not code and encountered_add_phone:
            self._print("[OAuth] consent 无法获取 code, add-phone 处理失败")

        if not code:
            self._print("[OAuth] 未获取到 authorization code")
            return None

        self._print("[OAuth] 7/7 POST /oauth/token")
        token_resp = self.session.post(f"{OAUTH_ISSUER}/oauth/token",
                                       headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": self.ua},
                                       data={"grant_type": "authorization_code", "code": code,
                                             "redirect_uri": OAUTH_REDIRECT_URI, "client_id": OAUTH_CLIENT_ID,
                                             "code_verifier": code_verifier},
                                       timeout=60, impersonate=self.impersonate)
        self._print(f"[OAuth] /oauth/token -> {token_resp.status_code}")

        if token_resp.status_code != 200:
            self._print(f"[OAuth] token 交换失败: {token_resp.text[:200]}")
            return None

        try:
            data = token_resp.json()
        except Exception:
            return None
        if not data.get("access_token"):
            return None

        self._print("[OAuth] Codex Token 获取成功 ✅")
        return data


# ================= 并发批量注册 =================

def _register_one(idx, total, proxy, output_file, stop_event=None):
    """单个注册任务（线程内运行）：DuckMail 创建 → 注册 → Team 邀请 → Codex OAuth"""
    def _stopped():
        return stop_event and stop_event.is_set()

    reg = None
    mail_token = None  # 用于 finally 中清理临时邮箱
    _registration_succeeded = False  # 注册步骤是否完成（用于判断 finally 中是否保留邮箱）
    result = (False, None, "未知错误")
    try:
        if _stopped():
            return False, None, "任务已停止"

        # SingBox: 使用已锁定的节点（由 run_batch 在批次开始前锁定）
        if proxy == "singbox://":
            try:
                from src.services.singbox import get_singbox_proxy, get_status, is_enabled
                if is_enabled():
                    status = get_status()
                    node_count = status.get("node_count", 0)
                    current = status.get("current_node") or "-"
                    proxy = get_singbox_proxy()
                    print(f"[SingBox] 开始注册: [{idx}/{total}] | 节点 {current} | 节点池 {node_count}")
                else:
                    print(f"[SingBox] 警告: sing-box 未运行, 使用直连")
                    proxy = None
            except Exception as e:
                print(f"[SingBox] 获取代理异常: {e}, 使用直连")
                proxy = None

        reg = ChatGPTRegister(proxy=proxy, tag=f"{idx}")

        # 0. 检测代理出口 IP 及地区（每个线程每个号都检测一次）
        with _print_lock:
            print(f"\n[线程-{idx}] 正在检测出口 IP ...")
        ip_info = _detect_proxy_ip_info(proxy)
        with _print_lock:
            print(f"[线程-{idx}] 出口 IP: {ip_info}")
        # 同时通过 SSE 广播给前端 Web 面板
        try:
            from src.services.logger import broadcast_log
            broadcast_log(f"[线程-{idx}] 出口 IP: {ip_info}")
        except Exception:
            pass

        # 1. 创建临时邮箱
        reg._print("[邮箱] 创建临时邮箱...")
        email, email_pwd, mail_token = reg.create_temp_email()
        tag = email.split("@")[0]
        reg.tag = tag

        if _stopped():
            result = (False, None, "任务已停止")
            return result

        chatgpt_password = _generate_password()
        name = _random_name()
        birthdate = _random_birthdate()

        with _print_lock:
            print(f"\n{'='*60}")
            print(f"  [{idx}/{total}] 注册: {email}")
            print(f"  出口 IP: {ip_info}")
            print(f"  ChatGPT密码: {chatgpt_password}")
            print(f"  邮箱密码: {email_pwd}")
            print(f"  姓名: {name} | 生日: {birthdate}")
            print(f"{'='*60}")

        # 2. 执行注册流程 (统一 V2: OAuth 直连)
        reg.run_register(email, chatgpt_password, name, birthdate, mail_token)

        if _stopped():
            result = (False, None, "任务已停止")
            return result

        # 3. Codex OAuth（优先从注册会话直接提取, 失败回退独立 OAuth 登录）
        oauth_ok = True
        if ENABLE_OAUTH:
            # 3a. 优先: 从注册会话直接提取 auth code 并换取 token
            reg._print("[OAuth] 从注册会话提取 Token...")
            tokens = reg.exchange_tokens_from_registration()
            
            # 3b. 回退: 如果注册会话提取失败, 使用独立 OAuth 登录（复用 reg 的 session 保持 cookies）
            if not tokens or not tokens.get("access_token"):
                reg._print("[OAuth] 注册会话提取失败，回退到独立 OAuth 登录（复用 session）...")
                tokens = reg.perform_codex_oauth_login_http(email, chatgpt_password, mail_token=mail_token)
            
            oauth_ok = bool(tokens and tokens.get("access_token"))
            if oauth_ok:
                _save_codex_tokens(email, tokens)
                reg._print("[OAuth] Token 已保存 ✅")
            else:
                reg._print("[OAuth] Codex Token 获取失败（可能因 add-phone），账号已创建，保存到已注册列表")

        if _stopped():
            result = (False, None, "任务已停止")
            return result

        # 4. 保存结果（无论 OAuth 是否成功，注册成功的账号都保存）
        oauth_label = "ok" if oauth_ok else "no_codex"
        with _file_lock:
            with open(output_file, "a", encoding="utf-8") as out:
                out.write(f"{email}----{chatgpt_password}----{email_pwd}----oauth={oauth_label}\n")

        save_to_csv(email, chatgpt_password, email_pwd, oauth_status=oauth_label)

        # 标记注册成功（供 finally 判断是否删邮箱）
        _registration_succeeded = True

        if oauth_ok:
            with _print_lock:
                print(f"\n[OK] [{tag}] {email} 注册成功 + Codex Token 获取成功! 🎉")
        else:
            with _print_lock:
                print(f"\n[OK] [{tag}] {email} 注册成功 (Codex Token 未获取，可能需要手机验证)")

        result = (True, email, None)
        return result

    except Exception as e:
        error_msg = str(e)
        with _print_lock:
            print(f"\n[FAIL] [{idx}] 注册失败: {error_msg}")
            traceback.print_exc()
        result = (False, None, error_msg)
        return result

    finally:
        # 只在注册完全失败时才删除临时邮箱；注册成功的保留（即使 OAuth 失败）
        if MAIL_PROVIDER == "cloudflare" and mail_token and reg:
            if not _registration_succeeded:
                reg._delete_temp_email_cf(mail_token)
            else:
                reg._print("📧 注册成功，保留临时邮箱")


def run_batch(total_accounts: int = 4, output_file="registered_accounts.txt",
              max_workers=1, proxy=None, stop_event=None):
    """并发批量注册 - 临时邮箱 + Codex OAuth"""
    # 检查邮箱提供商配置
    if MAIL_PROVIDER == "yyds_mail":
        if not YYDS_MAIL_API_KEY:
            print("❌ 错误: 未设置 YYDS_MAIL_API_KEY")
            return
    elif MAIL_PROVIDER == "cloudflare":
        if not CF_MAIL_ADMIN_PASSWORD and not CF_MAIL_JWT_SECRET:
            print("❌ 错误: 未设置 cf_mail_admin_password")
            return
    elif MAIL_PROVIDER == "mailapi_icu":
        if (not MAILAPI_ICU_EMAIL or not MAILAPI_ICU_ORDER_NO) and not MAILAPI_ICU_BULK:
            print("❌ 错误: 未设置 mailapi_icu_email 或 mailapi_icu_order_no，且批量池为空")
            return
    else:
        if not DUCKMAIL_BEARER:
            print("❌ 错误: 未设置 DUCKMAIL_BEARER")
            return

    # 代理回退：如果未指定代理，使用 config.json 里的全局默认代理
    if not proxy:
        proxy = DEFAULT_PROXY

    actual_workers = min(max_workers, total_accounts)
    print(f"\n{'#'*60}")
    print(f"  ChatGPT 批量自动注册 (纯协议版)")
    print(f"  注册数量: {total_accounts} | 并发数: {actual_workers}")
    print(f"  网络代理: {proxy or '(直连/无代理)'}")  # 打印实际使用的代理，方便排查
    mail_info = {"duckmail": DUCKMAIL_API_BASE, "cloudflare": CF_MAIL_API_BASE, "yyds_mail": YYDS_MAIL_API_BASE, "mailapi_icu": MAILAPI_ICU_EMAIL}
    print(f"  邮箱渠道: {MAIL_PROVIDER} | {mail_info.get(MAIL_PROVIDER, 'N/A')}")
    if MAIL_PROVIDER == "yyds_mail" and YYDS_MAIL_DOMAINS:
        print(f"  YYDS 域名池: {', '.join(YYDS_MAIL_DOMAINS)}")
    print(f"  OAuth: {'开启' if ENABLE_OAUTH else '关闭'} | required: {'是' if OAUTH_REQUIRED else '否'}")
    if ENABLE_OAUTH:
        print(f"  OAuth Issuer: {OAUTH_ISSUER}")
        print(f"  OAuth Client: {OAUTH_CLIENT_ID}")
        print(f"  Token输出: {TOKEN_JSON_DIR}/, {AK_FILE}, {RK_FILE}")
    print(f"  输出文件: {output_file}")
    print(f"{'#'*60}\n")

    # SingBox 模式: 批次开始前检测连通性并锁定节点
    if proxy == "singbox://":
        try:
            from src.services.singbox import ensure_usable_node, unpin_node
            node_name, proxy_addr = ensure_usable_node()
            if node_name:
                print(f"[SingBox] 本轮注册锁定节点: {node_name} ({proxy_addr})")
            else:
                print(f"[SingBox] 无可用节点，将使用直连")
        except Exception as e:
            print(f"[SingBox] 节点检测异常: {e}")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    # total_accounts 代表"成功数量"目标，失败自动补充，最多尝试 total_accounts*3 次防止无限循环
    max_attempts = total_accounts * 3
    attempt_idx = 0
    pending = set()

    executor = ThreadPoolExecutor(max_workers=actual_workers)
    try:
        # 初始填满 worker 池
        initial = min(actual_workers, max_attempts)
        while attempt_idx < initial:
            attempt_idx += 1
            f = executor.submit(_register_one, attempt_idx, total_accounts, proxy, output_file, stop_event)
            pending.add(f)

        while pending:
            if stop_event and stop_event.is_set():
                break

            done, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)

            for future in done:
                try:
                    ok, email, err = future.result()
                    if ok:
                        success_count += 1
                    else:
                        fail_count += 1
                        if err != "任务已停止":
                            print(f"  [第{attempt_idx}次尝试] 失败: {err}")
                except Exception as e:
                    fail_count += 1
                    with _print_lock:
                        print(f"[FAIL] 线程异常: {e}")

                # 达到成功目标，取消剩余排队任务
                if success_count >= total_accounts:
                    for pf in pending:
                        pf.cancel()
                    pending.clear()
                    break

                # 未达目标且未超最大尝试次数，补充新任务
                if (success_count < total_accounts
                        and attempt_idx < max_attempts
                        and not (stop_event and stop_event.is_set())):
                    attempt_idx += 1
                    new_f = executor.submit(_register_one, attempt_idx, total_accounts, proxy, output_file, stop_event)
                    pending.add(new_f)

    finally:
        # wait=False: 不等待运行中的线程；cancel_futures=True: 取消排队中的任务
        executor.shutdown(wait=False, cancel_futures=True)
        # SingBox: 解锁节点
        if proxy == "singbox://":
            try:
                from src.services.singbox import unpin_node
                unpin_node()
            except Exception:
                pass
        if stop_event and stop_event.is_set():
            print("⚠️ 任务已强制停止")

    elapsed = time.time() - start_time
    avg = elapsed / attempt_idx if attempt_idx else 0
    print(f"\n{'#'*60}")
    print(f"  注册完成! 耗时 {elapsed:.1f} 秒")
    print(f"  成功目标: {total_accounts} | 实际成功: {success_count} | 失败/重试: {fail_count} | 总尝试: {attempt_idx}")
    print(f"  平均速度: {avg:.1f} 秒/次")
    if success_count > 0:
        print(f"  结果文件: {output_file}")
    print(f"{'#'*60}")


def main():
    print("=" * 60)
    print("  ChatGPT 批量自动注册工具 (纯协议版)")
    print("  注册 → Codex OAuth 全流程自动化")
    print("=" * 60)

    if MAIL_PROVIDER == "yyds_mail" and not YYDS_MAIL_API_KEY:
        print("\n⚠️  警告: 未设置 YYDS_MAIL_API_KEY")
        print("   请编辑 config.json 设置 yyds_mail_api_key")
        print("   按 Enter 继续...")
        input()
    elif MAIL_PROVIDER == "duckmail" and not DUCKMAIL_BEARER:
        print("\n⚠️  警告: 未设置 DUCKMAIL_BEARER")
        print("   请编辑 config.json 设置 duckmail_bearer")
        print("   按 Enter 继续...")
        input()

    proxy = DEFAULT_PROXY
    if proxy:
        print(f"[Info] 使用代理: {proxy}")
    else:
        env_proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
                     or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy"))
        if env_proxy:
            print(f"[Info] 检测到环境变量代理: {env_proxy}")
            proxy = env_proxy
        else:
            proxy_input = input("输入代理地址 (留空=不使用代理): ").strip()
            proxy = proxy_input or None

    if proxy:
        print(f"[Info] 使用代理: {proxy}")

    count_input = input(f"\n注册账号数量 (默认 {DEFAULT_TOTAL_ACCOUNTS}): ").strip()
    total_accounts = int(count_input) if count_input.isdigit() and int(count_input) > 0 else DEFAULT_TOTAL_ACCOUNTS

    workers_input = input("并发数 (默认 1): ").strip()
    max_workers = int(workers_input) if workers_input.isdigit() and int(workers_input) > 0 else 1

    run_batch(total_accounts=total_accounts, output_file=DEFAULT_OUTPUT_FILE,
              max_workers=max_workers, proxy=proxy)


if __name__ == "__main__":
    main()
