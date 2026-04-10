import yaml

CONFIG_NODE_TYPES = {"vmess", "vless", "trojan", "ss", "ssr", "hysteria2", "hy2", "tuic", "http", "socks5"}


def parse_clash_payload(text):
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Clash YAML 解析失败: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("远程返回看起来是 Clash YAML，但根对象不是映射")

    proxies = payload.get("proxies")
    if not isinstance(proxies, list):
        raise ValueError("Clash YAML 中未找到 proxies 列表")

    nodes = []
    skipped = {}
    for proxy in proxies:
        node = _convert_proxy(proxy)
        if node is not None:
            nodes.append(node)
            continue
        proxy_type = str((proxy or {}).get("type") or "").strip().lower() or "unknown"
        skipped[proxy_type] = skipped.get(proxy_type, 0) + 1
    return nodes, _build_warnings(skipped)


def looks_like_clash_yaml(text):
    stripped = (text or "").strip()
    return "proxies:" in stripped and "\n" in stripped


def _convert_proxy(proxy):
    if not isinstance(proxy, dict):
        return None
    proxy_type = str(proxy.get("type") or "").strip().lower()
    if proxy_type not in CONFIG_NODE_TYPES:
        return None
    converters = {
        "http": _convert_http,
        "hysteria2": _convert_hysteria2,
        "hy2": _convert_hysteria2,
        "socks5": _convert_socks5,
        "ss": _convert_shadowsocks,
        "ssr": _convert_shadowsocks,
        "trojan": _convert_trojan,
        "tuic": _convert_tuic,
        "vless": _convert_vless,
        "vmess": _convert_vmess,
    }
    return converters.get(proxy_type, _convert_passthrough)(proxy)


def _convert_vmess(proxy):
    node = _base_node(proxy, "vmess")
    node["uuid"] = proxy.get("uuid", "")
    node["alter_id"] = int(proxy.get("alterId", proxy.get("alter-id", 0)) or 0)
    node["security"] = proxy.get("cipher", "auto")
    _apply_tls(node, proxy)
    _apply_transport(node, proxy)
    return node


def _convert_vless(proxy):
    node = _base_node(proxy, "vless")
    node["uuid"] = proxy.get("uuid", "")
    flow = proxy.get("flow", "")
    if flow:
        node["flow"] = flow
    _apply_tls(node, proxy)
    _apply_transport(node, proxy)
    return node


def _convert_trojan(proxy):
    node = _base_node(proxy, "trojan")
    node["password"] = proxy.get("password", "")
    _apply_tls(node, proxy, default_enabled=True)
    _apply_transport(node, proxy)
    return node


def _convert_shadowsocks(proxy):
    node = _base_node(proxy, "shadowsocks")
    node["method"] = proxy.get("cipher", "")
    node["password"] = proxy.get("password", "")
    return node


def _convert_hysteria2(proxy):
    node = _base_node(proxy, "hysteria2")
    node["password"] = proxy.get("password", "")
    node["tls"] = _build_tls(proxy, default_enabled=True)
    obfs = proxy.get("obfs", "")
    obfs_password = proxy.get("obfs-password", "")
    if obfs == "salamander" and obfs_password:
        node["obfs"] = {"type": "salamander", "password": obfs_password}
    return node


def _convert_tuic(proxy):
    node = _base_node(proxy, "tuic")
    node["uuid"] = proxy.get("uuid", "")
    node["password"] = proxy.get("password", "")
    node["congestion_control"] = proxy.get("congestion-controller") or proxy.get("congestion_control") or "bbr"
    node["udp_relay_mode"] = proxy.get("udp-relay-mode") or proxy.get("udp_relay_mode") or "native"
    node["tls"] = _build_tls(proxy, default_enabled=True)
    return node


def _convert_http(proxy):
    node = _base_node(proxy, "http")
    if proxy.get("username"):
        node["username"] = proxy.get("username")
    if proxy.get("password"):
        node["password"] = proxy.get("password")
    if _is_truthy(proxy.get("tls")):
        node["tls"] = _build_tls(proxy, default_enabled=True)
    return node


def _convert_socks5(proxy):
    node = _base_node(proxy, "socks")
    if proxy.get("username"):
        node["username"] = proxy.get("username")
    if proxy.get("password"):
        node["password"] = proxy.get("password")
    return node


def _convert_passthrough(proxy):
    node = _base_node(proxy, proxy.get("type", "node"))
    if _is_truthy(proxy.get("tls")):
        node["tls"] = _build_tls(proxy, default_enabled=True)
    return node


def _base_node(proxy, node_type):
    return {
        "type": node_type,
        "tag": proxy.get("name") or proxy.get("tag") or f"{node_type}-{proxy.get('server', 'node')}",
        "server": proxy.get("server", ""),
        "server_port": int(proxy.get("port", 0) or 0),
    }


def _apply_tls(node, proxy, default_enabled=False):
    tls = _build_tls(proxy, default_enabled=default_enabled)
    if tls["enabled"]:
        node["tls"] = tls
    reality = proxy.get("reality-opts") or {}
    if not isinstance(reality, dict) or not reality:
        return
    node["tls"] = tls
    node["tls"]["reality"] = {
        "enabled": True,
        "public_key": reality.get("public-key", ""),
        "short_id": reality.get("short-id", ""),
    }
    fingerprint = proxy.get("client-fingerprint", "")
    if fingerprint:
        node["tls"]["utls"] = {"enabled": True, "fingerprint": fingerprint}


def _build_tls(proxy, default_enabled=False):
    enabled = default_enabled or _is_truthy(proxy.get("tls")) or bool(proxy.get("servername")) or bool(proxy.get("sni"))
    tls = {
        "enabled": enabled,
        "server_name": proxy.get("servername") or proxy.get("sni") or proxy.get("server", ""),
        "insecure": _is_truthy(proxy.get("skip-cert-verify", True)),
    }
    alpn = proxy.get("alpn")
    if isinstance(alpn, list) and alpn:
        tls["alpn"] = [str(item) for item in alpn if str(item)]
    elif isinstance(alpn, str) and alpn.strip():
        tls["alpn"] = [item.strip() for item in alpn.split(",") if item.strip()]
    return tls


def _apply_transport(node, proxy):
    network = str(proxy.get("network") or "").strip().lower()
    if network == "ws":
        ws_opts = proxy.get("ws-opts") or {}
        headers = ws_opts.get("headers") if isinstance(ws_opts, dict) else {}
        host = headers.get("Host") if isinstance(headers, dict) else proxy.get("servername", "")
        node["transport"] = {"type": "ws", "path": _nested_value(ws_opts, "path", "/")}
        if host:
            node["transport"]["headers"] = {"Host": host}
        return
    if network == "grpc":
        grpc_opts = proxy.get("grpc-opts") or {}
        node["transport"] = {
            "type": "grpc",
            "service_name": _nested_value(grpc_opts, "grpc-service-name", ""),
        }
        return
    if network in {"http", "h2"}:
        h2_opts = proxy.get("h2-opts") or {}
        host = _nested_value(h2_opts, "host", [])
        if isinstance(host, str):
            host = [host]
        node["transport"] = {
            "type": "http",
            "host": host,
            "path": _nested_value(h2_opts, "path", "/"),
        }


def _nested_value(mapping, key, default):
    if not isinstance(mapping, dict):
        return default
    return mapping.get(key, default)


def _is_truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _build_warnings(skipped):
    if not skipped:
        return []
    pairs = [f"{name} x{count}" for name, count in sorted(skipped.items())]
    return [f"检测到未支持的 Clash 节点类型: {', '.join(pairs)}"]
