"""
SingBox 代理服务模块
- 解析订阅地址 (vmess/vless/trojan/ss/hysteria2)
- 生成 sing-box 配置并启动进程
- 通过 Clash API 随机切换节点
"""

import base64
import json
import os
import random
import socket
import subprocess
import threading
import time
import urllib.parse
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.services.logger import broadcast_log
from src.services.singbox_subscription import inspect_subscription_reference

# ─── 全局状态 ───
_singbox_process = None
_singbox_lock = threading.RLock()
_current_nodes = []          # 当前加载的节点列表 (outbound dicts)
_current_node_name = None    # 当前选中的节点名
_config_path = None          # 临时配置文件路径
_healthy_node_names = []     # 最近一次 batch_test 通过的有效节点名
_node_pinned = False         # 节点是否被锁定（单轮注册期间不切换）

_listen_port = 10810
_api_port = 9090
SINGBOX_HEALTHCHECK_TIMEOUT_MS = 2000
SINGBOX_HEALTHCHECK_URL = "https://auth.openai.com/"
SINGBOX_MAX_SWITCH_ATTEMPTS = 5
SINGBOX_BATCH_TEST_URL = "https://www.google.com/"
SINGBOX_BATCH_TEST_TIMEOUT_MS = 3000
SINGBOX_NODE_SWITCH_SETTLE_SECONDS = 0.2


def _log(msg):
    """同时 print（被子进程 Queue 捕获）和 broadcast_log（主进程 SSE）"""
    try:
        print(msg)
    except UnicodeEncodeError:
        safe_msg = msg.encode('ascii', errors='backslashreplace').decode('ascii')
        print(safe_msg)
    try:
        broadcast_log(msg)
    except Exception:
        pass


# ════════════════════════════════════════
# 公开接口
# ════════════════════════════════════════

def is_enabled():
    """sing-box 进程是否正在运行"""
    process = _singbox_process
    if process is not None and process.poll() is None:
        return True
    return _is_controller_ready()


def get_singbox_proxy():
    """返回本地代理地址"""
    return f"http://127.0.0.1:{_listen_port}"


def pin_current_node():
    """锁定当前节点，防止其他线程切换"""
    global _node_pinned
    _node_pinned = True
    _log(f"[SingBox] 节点已锁定: {_current_node_name or '(无)'}")


def unpin_node():
    """解锁节点，允许切换"""
    global _node_pinned
    _node_pinned = False
    _log("[SingBox] 节点已解锁")


def ensure_usable_node(test_url=None):
    """确保当前节点可用，不可用则自动切换到可用节点。返回 (node_name, proxy_addr) 或 (None, None)。

    用于一轮注册开始前：先检测 → 可用就锁定 → 整轮复用。
    """
    if not is_enabled():
        return None, None

    # 先测试当前节点
    current = _current_node_name
    if current:
        delay = _probe_node_delay(current, test_url=test_url)
        if delay is not None:
            _log(f"[SingBox] 当前节点 {current} 可用 ({delay}ms)，锁定使用")
            pin_current_node()
            return current, get_singbox_proxy()
        _log(f"[SingBox] 当前节点 {current} 不可用，尝试切换...")

    # 当前不可用，自动切换
    new_node = switch_random_node()
    if new_node:
        pin_current_node()
        return new_node, get_singbox_proxy()

    _log("[SingBox] 无可用节点")
    return None, None


def get_status():
    """返回运行状态信息"""
    running = is_enabled()
    runtime = _read_runtime_status_from_controller() if running else {}
    return {
        "running": running,
        "node_count": runtime.get("node_count", len(_current_nodes)),
        "current_node": runtime.get("current_node", _current_node_name) if running else None,
        "listen_port": _listen_port,
        "api_port": _api_port,
    }


def get_runtime_node_names():
    if not is_enabled():
        return []
    return _load_node_names_from_controller()


def format_runtime_node_log(context):
    status = get_status()
    if not status.get("running"):
        return f"[SingBox] {context}: sing-box 未运行"
    current_node = status.get("current_node") or "-"
    node_count = status.get("node_count", 0)
    return f"[SingBox] {context}: 当前节点 {current_node} | 节点池 {node_count}"


def parse_subscription(url, proxy=None):
    """获取订阅地址内容，解析为 sing-box outbound 列表"""
    details = inspect_subscription(url, proxy=proxy)
    return details["nodes"]


def inspect_subscription(url, proxy=None):
    return inspect_subscription_reference(url, _parse_uri, proxy=proxy)


def start_singbox(nodes, listen_port=None, api_port=None):
    """生成配置并启动 sing-box 进程"""
    global _singbox_process, _current_nodes, _current_node_name, _config_path
    global _listen_port, _api_port

    if listen_port:
        _listen_port = listen_port
    if api_port:
        _api_port = api_port

    with _singbox_lock:
        if is_enabled():
            stop_singbox()
            # Windows 上端口释放需要时间，等待 TCP socket 完全关闭
            _wait_for_port_release(_listen_port, timeout=5)

        _current_nodes = nodes
        _current_node_name = nodes[0]["tag"] if nodes else None

        config = _build_config(nodes)
        fd, _config_path = tempfile.mkstemp(suffix=".json", prefix="singbox_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        exe = os.path.join(os.path.dirname(__file__), "..", "..", "core", "sing-box.exe")
        exe = os.path.normpath(exe)

        if not os.path.isfile(exe):
            raise FileNotFoundError(f"sing-box.exe 不存在: {exe}")

        _singbox_process = subprocess.Popen(
            [exe, "run", "-c", _config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        # 等待进程启动
        time.sleep(1.5)
        if _singbox_process.poll() is not None:
            stderr = _singbox_process.stderr.read().decode(errors="replace")
            _singbox_process = None
            raise RuntimeError(f"sing-box 启动失败: {stderr[:500]}")

        _log(f"[SingBox] sing-box 已启动, PID={_singbox_process.pid}, "
             f"代理端口={_listen_port}, 节点数={len(nodes)}")
    return True


def stop_singbox():
    """停止 sing-box 进程"""
    global _singbox_process, _current_node_name, _config_path
    with _singbox_lock:
        killed_managed = False
        if _singbox_process:
            pid = _singbox_process.pid
            # Windows 上必须杀整个进程树，否则子进程继续占用端口
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                killed_managed = True
            except Exception:
                # fallback: 直接 kill 主进程
                try:
                    _singbox_process.kill()
                    killed_managed = True
                except Exception:
                    pass
            try:
                _singbox_process.wait(timeout=5)
            except Exception:
                pass
            _singbox_process = None

        # 清理残留的 sing-box 进程（应用重启后 _singbox_process 丢失的情况）
        _kill_all_singbox_processes()

        if killed_managed:
            _log("[SingBox] sing-box 已停止")
        elif not _is_controller_ready():
            _log("[SingBox] sing-box 已停止")
        else:
            _log("[SingBox] sing-box 停止异常，可能有残留进程")

        if _config_path and os.path.isfile(_config_path):
            try:
                os.remove(_config_path)
            except Exception:
                pass
            _config_path = None

        _current_node_name = None


def switch_random_node():
    """通过 Clash API 随机切换节点，优先从已测试有效的节点池中选择"""
    if not is_enabled():
        return None

    # 节点被锁定时不切换，返回当前节点
    if _node_pinned:
        _log(f"[SingBox] 节点已锁定，保持 {_current_node_name}")
        return _current_node_name

    # 优先使用经过 batch_test 验证的有效节点
    candidates = list(_healthy_node_names) if _healthy_node_names else []
    all_names = _list_available_node_names()

    if not candidates:
        candidates = list(all_names)
    if not candidates:
        return None

    random.shuffle(candidates)
    attempts = candidates[:SINGBOX_MAX_SWITCH_ATTEMPTS]

    for node_name in attempts:
        delay = _probe_node_delay(node_name)
        if delay is None:
            _log(f"[SingBox] 跳过不可用节点 -> {node_name}")
            # 从有效池中移除已失效的节点
            if node_name in _healthy_node_names:
                _healthy_node_names.remove(node_name)
            continue
        if _select_node(node_name, delay_ms=delay):
            return node_name

    # 所有候选都失败，尝试全量节点中未试过的
    tried = set(attempts)
    fallback = [n for n in all_names if n not in tried]
    random.shuffle(fallback)
    for node_name in fallback[:SINGBOX_MAX_SWITCH_ATTEMPTS]:
        delay = _probe_node_delay(node_name)
        if delay is not None and _select_node(node_name, delay_ms=delay):
            return node_name

    # 完全无可用节点，返回 None
    _log("[SingBox] 所有节点均不可用")
    return None


def batch_test_nodes(nodes, test_url=None):
    """并发测试所有节点"""
    global _healthy_node_names
    if not is_enabled():
        raise RuntimeError("SingBox 未运行")

    target_url = test_url or SINGBOX_BATCH_TEST_URL
    
    # 限制并发数
    max_workers = min(len(nodes), 15) if nodes else 1
    results_map = {}

    # 并发测试所有节点，不阻塞全局节点切换
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tag = {
            executor.submit(_probe_node, node.get("tag"), target_url, SINGBOX_BATCH_TEST_TIMEOUT_MS): node.get("tag")
            for node in nodes if node.get("tag")
        }
        
        for future in as_completed(future_to_tag):
            tag = future_to_tag[future]
            try:
                results_map[tag] = future.result()
            except Exception as e:
                results_map[tag] = _build_probe_failure(str(e))

    # 汇总结果，保持原始顺序
    results = []
    available_nodes = []
    best_result = None
    
    for node in nodes:
        tag = node.get("tag")
        if not tag or tag not in results_map:
            continue
        
        result = {"tag": tag, **results_map[tag]}
        results.append(result)
        
        if result["ok"]:
            available_nodes.append(node)
            if best_result is None or result["elapsed_ms"] < best_result["elapsed_ms"]:
                best_result = result
            _log(f"[SingBox] 节点测试通过 -> {tag} ({result['elapsed_ms']} ms)")
        else:
            _log(f"[SingBox] 节点测试失败 -> {tag} ({result['error']})")

    if best_result:
        _select_node(best_result["tag"], delay_ms=best_result["elapsed_ms"])

    # 更新有效节点池
    _healthy_node_names = [n.get("tag") for n in available_nodes if n.get("tag")]
    _log(f"[SingBox] 节点测试完成: 有效 {len(_healthy_node_names)}/{len(nodes)}")

    return {
        "available_nodes": available_nodes,
        "best_node": best_result["tag"] if best_result else None,
        "results": results,
        "test_url": target_url,
    }


def _is_probe_success_status(status_code):
    return isinstance(status_code, int) and 200 <= status_code < 500


def _probe_timeout_seconds(timeout_ms):
    return max(1.0, timeout_ms / 1000)


def _build_probe_failure(error, status_code=None, elapsed_ms=None):
    return {
        "ok": False,
        "elapsed_ms": elapsed_ms,
        "status_code": status_code,
        "error": error,
    }


def _format_probe_exception(exc):
    return f"{exc.__class__.__name__}: {exc}"


def _parse_probe_target(test_url):
    parsed = urllib.parse.urlsplit(test_url)
    host = parsed.hostname
    if not parsed.scheme or not host:
        raise ValueError(f"非法测试地址: {test_url}")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"不支持的测试协议: {parsed.scheme}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    target = f"{host}:{port}"
    return parsed.scheme, host, port, target, test_url


def _probe_via_local_proxy(test_url, timeout_ms):
    """回退方案：使用 requests 通过本地代理测试（提高准确性）"""
    proxies = {
        "http": f"http://127.0.0.1:{_listen_port}",
        "https": f"http://127.0.0.1:{_listen_port}",
    }
    start = time.perf_counter()
    try:
        resp = requests.get(
            test_url,
            proxies=proxies,
            timeout=timeout_ms / 1000,
            stream=True,
            verify=False,
            allow_redirects=False,
        )
        resp.close()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if 200 <= resp.status_code < 500:
            return {
                'ok': True,
                'elapsed_ms': elapsed_ms,
                'status_code': resp.status_code,
                'error': '',
            }
        return _build_probe_failure(f'HTTP {resp.status_code}', resp.status_code, elapsed_ms)
    except Exception as exc:
        return _build_probe_failure(_format_probe_exception(exc))


def _probe_node(node_name, test_url=None, timeout_ms=None):
    """测试单个节点（优先使用 Clash API 的 delay 接口）"""
    target_url = test_url or SINGBOX_HEALTHCHECK_URL
    probe_timeout_ms = timeout_ms or SINGBOX_HEALTHCHECK_TIMEOUT_MS
    
    # 使用 Clash API 的 delay 接口进行针对性测试，不改变全局节点切换，且更准确
    try:
        quoted_name = urllib.parse.quote(node_name)
        url = f"http://127.0.0.1:{_api_port}/proxies/{quoted_name}/delay"
        params = {
            "timeout": int(probe_timeout_ms),
            "url": target_url
        }
        resp = requests.get(url, params=params, timeout=(probe_timeout_ms / 1000) + 2)
        if resp.status_code == 200:
            data = resp.json()
            delay = data.get("delay")
            if isinstance(delay, int) and delay > 0:
                return {
                    "ok": True,
                    "elapsed_ms": delay,
                    "status_code": 200,
                    "error": "",
                }
        
        error_msg = f"HTTP {resp.status_code}"
        try:
            error_msg = resp.json().get("message", error_msg)
        except:
            pass
        return _build_probe_failure(error_msg, status_code=resp.status_code)
    except Exception as e:
        # 如果 Clash API 不可用，不再回退到 _select_node 模式，直接返回失败以保证并发安全
        return _build_probe_failure(str(e))


def _is_controller_ready():
    try:
        resp = requests.get(
            f"http://127.0.0.1:{_api_port}/proxies",
            timeout=1.5,
        )
        if not resp.ok:
            return False
        data = resp.json()
        return isinstance(data, dict) and isinstance(data.get("proxies"), dict)
    except Exception:
        return False


def _read_runtime_status_from_controller():
    try:
        resp = requests.get(
            f"http://127.0.0.1:{_api_port}/proxies",
            timeout=1.5,
        )
        if not resp.ok:
            return {}
        data = resp.json()
        proxies = data.get("proxies") or {}
        selector = proxies.get("proxy") or {}
        names = selector.get("all") or []
        usable = [name for name in names if name and name != "direct"]
        return {
            "current_node": selector.get("now") or None,
            "node_count": len(usable),
        }
    except Exception:
        return {}


def _list_available_node_names():
    if _current_nodes:
        names = [node.get("tag") for node in _current_nodes if node.get("tag")]
        if names:
            return names
    return _load_node_names_from_controller()


def _load_node_names_from_controller():
    try:
        resp = requests.get(
            f"http://127.0.0.1:{_api_port}/proxies",
            timeout=1.5,
        )
        if not resp.ok:
            return []
        data = resp.json()
        proxies = data.get("proxies") or {}
        selector = proxies.get("proxy") or {}
        names = selector.get("all") or []
        return [name for name in names if name and name != "direct"]
    except Exception:
        return []


def _probe_node_delay(node_name, test_url=None, timeout_ms=None):
    result = _probe_node(node_name, test_url=test_url, timeout_ms=timeout_ms)
    if result["ok"]:
        return result["elapsed_ms"]
    return None


def _select_node(node_name, delay_ms=None):
    global _current_node_name
    try:
        resp = requests.put(
            f"http://127.0.0.1:{_api_port}/proxies/proxy",
            json={"name": node_name},
            timeout=3,
        )
        if resp.status_code == 204 or resp.ok:
            _current_node_name = node_name
            delay_text = f" ({delay_ms} ms)" if isinstance(delay_ms, int) else ""
            _log(f"[SingBox] 切换节点 -> {node_name}{delay_text}")
            return node_name
        _log(f"[SingBox] 切换节点失败: HTTP {resp.status_code}")
        return None
    except Exception as e:
        _log(f"[SingBox] 切换节点异常: {e}")
        return None


# ════════════════════════════════════════
# 内部: 配置生成
# ════════════════════════════════════════

def _build_config(nodes):
    """构造 sing-box JSON 配置"""
    outbound_tags = [n["tag"] for n in nodes]

    config = {
        "log": {"level": "warn"},
        "dns": {
            "servers": [
                {
                    "type": "https",
                    "tag": "proxy-dns",
                    "server": "1.1.1.1",
                    "domain_resolver": "local-dns",
                    "detour": "proxy",
                },
                {
                    "type": "udp",
                    "tag": "local-dns",
                    "server": "223.5.5.5",
                },
            ],
            "rules": [
                {
                    "domain_suffix": [
                        "google.com",
                        "googleapis.com",
                        "gstatic.com",
                        "google.co.jp",
                        "google.com.hk",
                        "googleusercontent.com",
                        "openai.com",
                        "chatgpt.com",
                        "oaistatic.com",
                        "oaiusercontent.com",
                    ],
                    "server": "proxy-dns",
                },
            ],
            "final": "local-dns",
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": _listen_port,
            }
        ],
        "outbounds": [
            {
                "type": "selector",
                "tag": "proxy",
                "outbounds": outbound_tags + ["direct"],
                "default": outbound_tags[0] if outbound_tags else "direct",
            },
            *nodes,
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "final": "proxy",
            "default_domain_resolver": "local-dns",
        },
        "experimental": {
            "clash_api": {
                "external_controller": f"127.0.0.1:{_api_port}",
                "default_mode": "rule",
            }
        },
    }
    return config


_node_counter = 0
_node_counter_lock = threading.Lock()


def _next_tag(prefix="node"):
    global _node_counter
    with _node_counter_lock:
        _node_counter += 1
        return f"{prefix}-{_node_counter}"


def _parse_uri(uri):
    """将代理协议 URI 解析为 sing-box outbound dict，不支持的返回 None"""
    if uri.startswith("vmess://"):
        return _parse_vmess(uri)
    elif uri.startswith("vless://"):
        return _parse_vless(uri)
    elif uri.startswith("trojan://"):
        return _parse_trojan(uri)
    elif uri.startswith("ss://"):
        return _parse_ss(uri)
    elif uri.startswith("tuic://"):
        return _parse_tuic(uri)
    elif uri.startswith(("hysteria2://", "hy2://")):
        return _parse_hysteria2(uri)
    return None


def _parse_vmess(uri):
    """vmess://base64json"""
    try:
        raw = uri[len("vmess://"):]
        padded = raw + "=" * (-len(raw) % 4)
        obj = json.loads(base64.b64decode(padded).decode("utf-8"))

        tag = obj.get("ps") or _next_tag("vmess")
        server = obj.get("add", "")
        port = int(obj.get("port", 443))
        uuid = obj.get("id", "")
        aid = int(obj.get("aid", 0))
        net = obj.get("net", "tcp")
        tls_val = obj.get("tls", "")
        sni = obj.get("sni") or obj.get("host", "")
        host = obj.get("host", "")
        path = obj.get("path", "")

        node = {
            "type": "vmess",
            "tag": tag,
            "server": server,
            "server_port": port,
            "uuid": uuid,
            "alter_id": aid,
            "security": obj.get("scy", "auto"),
        }

        # transport
        if net == "ws":
            node["transport"] = {
                "type": "ws",
                "path": path or "/",
                "headers": {"Host": host} if host else {},
            }
        elif net == "grpc":
            node["transport"] = {
                "type": "grpc",
                "service_name": path,
            }
        elif net == "h2":
            node["transport"] = {
                "type": "http",
                "host": [host] if host else [],
                "path": path or "/",
            }

        # TLS
        if tls_val == "tls":
            node["tls"] = {
                "enabled": True,
                "server_name": sni or server,
                "insecure": True,
            }

        return node
    except Exception:
        return None


def _parse_vless(uri):
    """vless://uuid@host:port?params#name"""
    try:
        rest = uri[len("vless://"):]
        fragment = ""
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            fragment = urllib.parse.unquote(fragment)

        userinfo, hostport_params = rest.split("@", 1)
        uuid = userinfo

        if "?" in hostport_params:
            hostport, query_str = hostport_params.split("?", 1)
        else:
            hostport, query_str = hostport_params, ""

        server, port_str = _split_host_port(hostport)
        port = int(port_str)
        params = dict(urllib.parse.parse_qsl(query_str))

        tag = fragment or _next_tag("vless")
        flow = params.get("flow", "")
        security = params.get("security", "none")
        net_type = params.get("type", "tcp")
        sni = params.get("sni", "")

        node = {
            "type": "vless",
            "tag": tag,
            "server": server,
            "server_port": port,
            "uuid": uuid,
        }
        if flow:
            node["flow"] = flow

        # TLS / Reality
        if security == "tls":
            node["tls"] = {
                "enabled": True,
                "server_name": sni or server,
                "insecure": True,
            }
            alpn = params.get("alpn")
            if alpn:
                node["tls"]["alpn"] = alpn.split(",")
        elif security == "reality":
            node["tls"] = {
                "enabled": True,
                "server_name": sni or server,
                "reality": {
                    "enabled": True,
                    "public_key": params.get("pbk", ""),
                    "short_id": params.get("sid", ""),
                },
                "utls": {
                    "enabled": True,
                    "fingerprint": params.get("fp", "chrome"),
                },
            }

        # Transport
        _apply_transport(node, net_type, params)
        return node
    except Exception:
        return None


def _parse_trojan(uri):
    """trojan://password@host:port?params#name"""
    try:
        rest = uri[len("trojan://"):]
        fragment = ""
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            fragment = urllib.parse.unquote(fragment)

        userinfo, hostport_params = rest.split("@", 1)
        password = urllib.parse.unquote(userinfo)

        if "?" in hostport_params:
            hostport, query_str = hostport_params.split("?", 1)
        else:
            hostport, query_str = hostport_params, ""

        server, port_str = _split_host_port(hostport)
        port = int(port_str)
        params = dict(urllib.parse.parse_qsl(query_str))

        tag = fragment or _next_tag("trojan")
        sni = params.get("sni", "")
        net_type = params.get("type", "tcp")

        node = {
            "type": "trojan",
            "tag": tag,
            "server": server,
            "server_port": port,
            "password": password,
            "tls": {
                "enabled": True,
                "server_name": sni or server,
                "insecure": True,
            },
        }

        _apply_transport(node, net_type, params)
        return node
    except Exception:
        return None


def _parse_ss(uri):
    """ss://base64(method:password)@host:port#name  或  ss://base64(method:password@host:port)#name"""
    try:
        rest = uri[len("ss://"):]
        fragment = ""
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            fragment = urllib.parse.unquote(fragment)

        # SIP002 格式: base64(method:password)@host:port
        if "@" in rest:
            userinfo, hostport = rest.rsplit("@", 1)
            try:
                padded = userinfo + "=" * (-len(userinfo) % 4)
                decoded = base64.b64decode(padded).decode("utf-8")
                method, password = decoded.split(":", 1)
            except Exception:
                method, password = userinfo.split(":", 1)
            server, port_str = _split_host_port(hostport)
        else:
            # 旧格式: base64(method:password@host:port)
            padded = rest + "=" * (-len(rest) % 4)
            decoded = base64.b64decode(padded).decode("utf-8")
            userinfo, hostport = decoded.rsplit("@", 1)
            method, password = userinfo.split(":", 1)
            server, port_str = _split_host_port(hostport)

        port = int(port_str)
        tag = fragment or _next_tag("ss")

        return {
            "type": "shadowsocks",
            "tag": tag,
            "server": server,
            "server_port": port,
            "method": method,
            "password": password,
        }
    except Exception:
        return None


def _parse_hysteria2(uri):
    """hysteria2://password@host:port?params#name"""
    try:
        rest = uri.split("://", 1)[1]
        fragment = ""
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            fragment = urllib.parse.unquote(fragment)

        userinfo, hostport_params = rest.split("@", 1)
        password = urllib.parse.unquote(userinfo)

        if "?" in hostport_params:
            hostport, query_str = hostport_params.split("?", 1)
        else:
            hostport, query_str = hostport_params, ""

        server, port_str = _split_host_port(hostport)
        port = int(port_str)
        params = dict(urllib.parse.parse_qsl(query_str))

        tag = fragment or _next_tag("hy2")
        sni = params.get("sni", "")
        obfs = params.get("obfs", "")
        obfs_password = params.get("obfs-password", "")

        node = {
            "type": "hysteria2",
            "tag": tag,
            "server": server,
            "server_port": port,
            "password": password,
            "tls": {
                "enabled": True,
                "server_name": sni or server,
                "insecure": True,
            },
        }

        if obfs == "salamander" and obfs_password:
            node["obfs"] = {
                "type": "salamander",
                "password": obfs_password,
            }

        return node
    except Exception:
        return None


def _parse_tuic(uri):
    """tuic://uuid:password@host:port?params#name"""
    try:
        rest = uri[len("tuic://"):]
        fragment = ""
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            fragment = urllib.parse.unquote(fragment)

        userinfo, hostport_params = rest.split("@", 1)
        if ":" not in userinfo:
            return None
        uuid, password = userinfo.split(":", 1)

        if "?" in hostport_params:
            hostport, query_str = hostport_params.split("?", 1)
        else:
            hostport, query_str = hostport_params, ""

        server, port_str = _split_host_port(hostport)
        port = int(port_str)
        params = dict(urllib.parse.parse_qsl(query_str))
        tag = fragment or _next_tag("tuic")

        node = {
            "type": "tuic",
            "tag": tag,
            "server": server,
            "server_port": port,
            "uuid": urllib.parse.unquote(uuid),
            "password": urllib.parse.unquote(password),
            "congestion_control": params.get("congestion_control", "bbr"),
            "udp_relay_mode": params.get("udp_relay_mode", "native"),
            "tls": {
                "enabled": True,
                "server_name": params.get("sni", "") or server,
                "insecure": True,
            },
        }

        alpn = params.get("alpn", "")
        if alpn:
            node["tls"]["alpn"] = [item for item in alpn.split(",") if item]
        return node
    except Exception:
        return None


# ─── 辅助 ───

def _kill_all_singbox_processes():
    """杀死所有 sing-box.exe 进程（清理残留/孤儿进程）"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "sing-box.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _wait_for_port_release(port, timeout=5):
    """等待端口释放（Windows 上进程退出后 TCP 端口可能仍被占用）"""
    import socket
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            sock.close()
            return  # 端口已可用
        except OSError:
            sock.close()
            time.sleep(0.3)
    # 超时仍占用 → 尝试查找并强杀占用端口的进程
    _force_kill_port(port)
    time.sleep(0.5)


def _force_kill_port(port):
    """强制杀死占用指定端口的进程（Windows）"""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in result.stdout.splitlines():
            if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) > 0:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", pid],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    _log(f"[SingBox] 强制终止占用端口 {port} 的进程 PID={pid}")
                    return
    except Exception:
        pass


def _split_host_port(hostport):
    """拆分 host:port，支持 IPv6 [::1]:port"""
    if hostport.startswith("["):
        bracket_end = hostport.index("]")
        host = hostport[1:bracket_end]
        port = hostport[bracket_end + 2:]  # skip ]:
    else:
        host, port = hostport.rsplit(":", 1)
    return host, port


def _apply_transport(node, net_type, params):
    """根据 type 参数添加 transport 配置"""
    if net_type == "ws":
        node["transport"] = {
            "type": "ws",
            "path": params.get("path", "/"),
        }
        host = params.get("host", "")
        if host:
            node["transport"]["headers"] = {"Host": host}
    elif net_type == "grpc":
        node["transport"] = {
            "type": "grpc",
            "service_name": params.get("serviceName", ""),
        }
    elif net_type in ("h2", "http"):
        node["transport"] = {
            "type": "http",
            "host": [params.get("host", "")],
            "path": params.get("path", "/"),
        }
