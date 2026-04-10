import os
from datetime import datetime

from src.utils.config import BASE_DIR, read_json_file, write_json_file

CACHE_PATH = os.path.join(BASE_DIR, "singbox_nodes_cache.json")


def load_cached_subscription(url):
    payload = read_json_file(CACHE_PATH, {})
    if payload.get("source_url") != url:
        return None
    if not isinstance(payload.get("nodes"), list):
        return None
    return payload


def save_cached_subscription(url, details):
    payload = {
        "cached_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(details["nodes"]),
        "nodes": details["nodes"],
        "payload_type": details["payload_type"],
        "profile_name": details["profile_name"],
        "source_type": details["source_type"],
        "source_url": url,
        "warnings": details["warnings"],
    }
    write_json_file(CACHE_PATH, payload)
    return payload


def get_cached_node_pool(url):
    payload = load_cached_subscription(url)
    if not payload:
        return None
    health_check = payload.get("health_check") or {}
    available_tags = health_check.get("available_tags")
    if not isinstance(available_tags, list):
        return payload["nodes"]
    available_set = set(available_tags)
    return [node for node in payload["nodes"] if node.get("tag") in available_set]


def update_cached_node_health(url, results, test_url):
    payload = load_cached_subscription(url)
    if not payload:
        return None
    available_tags = [item["tag"] for item in results if item.get("ok")]
    payload["health_check"] = {
        "tested_at": datetime.now().isoformat(timespec="seconds"),
        "test_url": test_url,
        "available_tags": available_tags,
        "results": results,
    }
    write_json_file(CACHE_PATH, payload)
    return payload
