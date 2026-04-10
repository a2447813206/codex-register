import base64
import copy
import json
import urllib.parse

import requests

from src.services.clash_subscription import looks_like_clash_yaml, parse_clash_payload

FETCH_TIMEOUT_SECONDS = 20
REMOTE_PROFILE_ACTION = "import-remote-profile"
REMOTE_PROFILE_SCHEME = "sing-box"
SUBSCRIPTION_USER_AGENT = "clash-verge/v2"

INLINE_COMMENT_PREFIXES = ("#", "//", ";")
CONFIG_GROUP_TYPES = {"selector", "urltest"}
CONFIG_IGNORED_TYPES = {"direct", "block", "dns"}
CONFIG_NODE_TYPES = {
    "anytls",
    "http",
    "hysteria2",
    "shadowsocks",
    "shadowtls",
    "socks",
    "ssh",
    "trojan",
    "tuic",
    "vless",
    "vmess",
    "wireguard",
}


def inspect_subscription_reference(reference, uri_parser, proxy=None):
    source = _resolve_subscription_source(reference)
    if source["source_type"] == "inline-node":
        return _inspect_inline_node(source, uri_parser)

    response = _fetch_subscription_response(source["fetch_url"], proxy)
    nodes, warnings, payload_type = _parse_subscription_payload(response["text"], uri_parser)
    if nodes:
        return _build_inspection_result(nodes, warnings, payload_type, source, response)

    message = _build_no_nodes_error(source, response, warnings, payload_type)
    raise ValueError(message)


def _resolve_subscription_source(reference):
    value = (reference or "").strip()
    if not value:
        raise ValueError("缺少订阅地址")
    if _is_remote_profile_link(value):
        return _resolve_remote_profile_source(value)
    if _is_remote_url(value):
        return {
            "input": value,
            "fetch_url": value,
            "profile_name": "",
            "source_type": "subscription-url",
        }
    return {
        "input": value,
        "fetch_url": "",
        "profile_name": "",
        "source_type": "inline-node",
    }


def _resolve_remote_profile_source(link):
    parsed = urllib.parse.urlsplit(link)
    action = (parsed.netloc or parsed.path.lstrip("/")).strip()
    if action != REMOTE_PROFILE_ACTION:
        raise ValueError(f"不支持的 sing-box 链接动作: {action or '(empty)'}")

    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    remote_url = (query.get("url") or [""])[0].strip()
    if not remote_url:
        raise ValueError("sing-box 远程配置链接缺少 url 参数")
    remote_url = urllib.parse.unquote(remote_url)
    if not _is_remote_url(remote_url):
        raise ValueError(f"sing-box 远程配置 url 非法: {remote_url}")

    return {
        "input": link,
        "fetch_url": remote_url,
        "profile_name": urllib.parse.unquote(parsed.fragment or "").strip(),
        "source_type": "remote-profile",
    }


def _inspect_inline_node(source, uri_parser):
    node = uri_parser(source["input"])
    if node is None:
        scheme = _extract_scheme(source["input"]) or "unknown"
        raise ValueError(f"不支持的节点协议: {scheme}")
    return _build_inspection_result([node], [], "inline-node", source, None)


def _fetch_subscription_response(url, proxy):
    proxies = _build_request_proxies(proxy)
    resp = requests.get(
        url,
        timeout=FETCH_TIMEOUT_SECONDS,
        proxies=proxies,
        verify=False,
        headers={"User-Agent": SUBSCRIPTION_USER_AGENT},
    )
    resp.raise_for_status()
    return {
        "content_type": (resp.headers.get("Content-Type") or "").strip(),
        "final_url": str(resp.url),
        "text": resp.text.strip(),
    }


def _build_request_proxies(proxy):
    if not proxy:
        return None
    value = proxy if "://" in proxy else f"http://{proxy}"
    return {"http": value, "https": value}


def _parse_subscription_payload(text, uri_parser):
    content = _strip_bom(text)
    if not content:
        return [], ["远程内容为空"], "empty"
    if _looks_like_json_payload(content):
        nodes, warnings = _parse_json_payload(content)
        return nodes, warnings, "json-config"
    if looks_like_clash_yaml(content):
        nodes, warnings = parse_clash_payload(content)
        return nodes, warnings, "clash-yaml"

    decoded = _try_decode_subscription_payload(content)
    if decoded:
        nodes, warnings = _parse_decoded_payload(decoded, uri_parser)
        payload_type = _detect_decoded_payload_type(decoded)
        return nodes, warnings, payload_type

    nodes, warnings = _parse_uri_lines(content.splitlines(), uri_parser)
    return nodes, warnings, "line-list"


def _parse_decoded_payload(decoded, uri_parser):
    content = _strip_bom(decoded)
    if _looks_like_json_payload(content):
        return _parse_json_payload(content)
    if looks_like_clash_yaml(content):
        return parse_clash_payload(content)
    return _parse_uri_lines(content.splitlines(), uri_parser)


def _parse_json_payload(text):
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"远程返回 JSON，但解析失败: {exc.msg}") from exc

    if isinstance(payload, dict):
        outbounds = payload.get("outbounds")
    elif isinstance(payload, list):
        outbounds = payload
    else:
        outbounds = None

    if not isinstance(outbounds, list):
        raise ValueError("远程返回的是 JSON，但未找到可用的 outbounds 列表")

    nodes = []
    skipped = {}
    for outbound in outbounds:
        _collect_json_outbound(nodes, skipped, outbound)
    warnings = _format_skipped_warning(skipped, "配置出站")
    return nodes, warnings


def _collect_json_outbound(nodes, skipped, outbound):
    if not isinstance(outbound, dict):
        return
    outbound_type = str(outbound.get("type") or "").strip().lower()
    if not outbound_type or outbound_type in CONFIG_GROUP_TYPES or outbound_type in CONFIG_IGNORED_TYPES:
        return
    if outbound_type not in CONFIG_NODE_TYPES:
        skipped[outbound_type] = skipped.get(outbound_type, 0) + 1
        return

    node = copy.deepcopy(outbound)
    if not node.get("tag"):
        node["tag"] = f"imported-{len(nodes) + 1}"
    nodes.append(node)


def _parse_uri_lines(lines, uri_parser):
    nodes = []
    skipped = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith(INLINE_COMMENT_PREFIXES):
            continue
        node = uri_parser(line)
        if node is not None:
            nodes.append(node)
            continue
        scheme = _extract_scheme(line)
        if scheme:
            skipped[scheme] = skipped.get(scheme, 0) + 1

    warnings = _format_skipped_warning(skipped, "节点协议")
    return nodes, warnings


def _format_skipped_warning(skipped, label):
    if not skipped:
        return []
    pairs = [f"{name} x{count}" for name, count in sorted(skipped.items())]
    return [f"检测到未支持的{label}: {', '.join(pairs)}"]


def _build_inspection_result(nodes, warnings, payload_type, source, response):
    result = {
        "count": len(nodes),
        "nodes": nodes,
        "payload_type": payload_type,
        "profile_name": source["profile_name"],
        "source_type": source["source_type"],
        "warnings": warnings,
    }
    if response:
        result["content_type"] = response["content_type"]
        result["final_url"] = response["final_url"]
    return result


def _build_no_nodes_error(source, response, warnings, payload_type):
    hint = _detect_payload_hint(response["text"], response["content_type"], payload_type)
    parts = ["未解析到任何节点"]
    if source["source_type"] == "remote-profile":
        parts.append("输入是 sing-box 远程配置链接")
    if hint:
        parts.append(hint)
    parts.extend(warnings)
    return "；".join(parts)


def _detect_payload_hint(text, content_type, payload_type):
    if "html" in (content_type or "").lower():
        return "远程返回了 HTML 页面，通常说明链接失效、被鉴权页拦截，或并非订阅直链"
    if payload_type in {"clash-yaml", "base64-clash-yaml"}:
        return "远程内容看起来是 Clash/Mihomo YAML，但其中没有可用的 proxies 节点"
    if payload_type in {"json-config", "base64-json"}:
        return "远程内容看起来是 JSON 配置，但其中没有可用的节点出站"
    snippet = _strip_bom(text)[:80].replace("\n", " ").replace("\r", " ")
    if snippet.startswith("<"):
        return "远程返回内容像网页而不是订阅"
    if snippet:
        return f"响应内容前 80 字符: {snippet}"
    return ""


def _try_decode_subscription_payload(text):
    compact = "".join(text.split())
    if not compact or "://" in compact:
        return None
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        decoded = _decode_base64_payload(compact, decoder)
        if decoded and _looks_like_subscription_payload(decoded):
            return decoded
    return None


def _decode_base64_payload(text, decoder):
    try:
        padded = text + "=" * (-len(text) % 4)
        return decoder(padded.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def _looks_like_subscription_payload(text):
    stripped = _strip_bom(text)
    if _looks_like_json_payload(stripped):
        return True
    if looks_like_clash_yaml(stripped):
        return True
    return "://" in stripped


def _looks_like_json_payload(text):
    stripped = _strip_bom(text)
    return stripped.startswith("{") or stripped.startswith("[")


def _detect_decoded_payload_type(text):
    stripped = _strip_bom(text)
    if _looks_like_json_payload(stripped):
        return "base64-json"
    if looks_like_clash_yaml(stripped):
        return "base64-clash-yaml"
    return "base64-lines"


def _strip_bom(text):
    return (text or "").lstrip("\ufeff").strip()


def _is_remote_profile_link(value):
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme.lower() == REMOTE_PROFILE_SCHEME


def _is_remote_url(value):
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme.lower() in {"http", "https"}


def _extract_scheme(value):
    parsed = urllib.parse.urlsplit(value.strip())
    return parsed.scheme.lower() if parsed.scheme else ""
