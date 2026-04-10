import queue
from flask import Blueprint, request, jsonify, Response

from src.utils.config import read_config, write_config, safe_int
from src.utils.account import (
    parse_accounts, write_accounts, delete_token_file, 
    export_tokens_zip, count_token_stats
)
from src.services.task import (
    start_registration_task, stop_registration_task, get_task_status,
)
from src.services.singbox import (
    batch_test_nodes, inspect_subscription, parse_subscription, start_singbox, stop_singbox,
    get_status as get_singbox_status,
    get_runtime_node_names,
)
from src.services.singbox_cache import (
    get_cached_node_pool, load_cached_subscription, save_cached_subscription, update_cached_node_health,
)
from src.services.logger import (
    register_subscriber, remove_subscriber, _log_lock,
    list_history_logs, get_history_log, delete_history_log,
    clear_current_log_session, broadcast_log
)

api_bp = Blueprint("api_bp", __name__)


# ── 横幅广告（后端下发，前端不可绕过）───────────────────────────────
_BANNER_CONFIG = {
    "text": "该源码仅支持邮箱----取件api  购买邮箱地址",
    "button_text": "前往购买",
    "button_url": "https://royp.online/",
}


@api_bp.route("/banner", methods=["GET"])
def get_banner():
    """返回横幅广告配置，前端必须调用此接口获取"""
    return jsonify(_BANNER_CONFIG)


def _same_node_tags(left_tags, right_tags):
    return len(left_tags) == len(right_tags) and set(left_tags) == set(right_tags)


def _api_success(data=None, message="ok", code=0):
    payload = {
        "success": True,
        "ok": True,
        "code": code,
        "message": message,
    }
    if data is not None:
        payload["data"] = data
    return jsonify(payload)


def _normalize_config_payload(cfg, existing_cfg=None):
    normalized = dict(cfg)
    return normalized

@api_bp.route("/config", methods=["GET"])
def get_config_api():
    config = read_config()
    config = _normalize_config_payload(config, existing_cfg=config)
    return _api_success({"config": config}, message="config fetched")

@api_bp.route("/config", methods=["POST"])
def save_config_api():
    incoming = request.get_json(force=True) or {}
    existing = read_config()
    cfg = {**existing, **incoming}
    cfg = _normalize_config_payload(cfg, existing_cfg=existing)
    write_config(cfg)
    saved_config = read_config()
    saved_config = _normalize_config_payload(saved_config, existing_cfg=cfg)
    return _api_success({"config": saved_config}, message="config saved")

@api_bp.route("/start", methods=["POST"])
def start_task_api():
    body = request.get_json(force=True) or {}
    count = int(body.get("count", 1))
    workers = int(body.get("workers", 1))
    proxy = body.get("proxy", "").strip() or None
    
    ok, err = start_registration_task(count, workers, proxy)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": err}), 409

@api_bp.route("/stop", methods=["POST"])
def stop_task_api():
    stop_registration_task()
    return jsonify({"ok": True})

@api_bp.route("/status", methods=["GET"])
def task_status_api():
    return jsonify(get_task_status())

@api_bp.route("/logs")
def sse_logs_api():
    q = queue.Queue(maxsize=2000)
    register_subscriber(q)

    def stream():
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                batch = [msg]
                while len(batch) < 50:
                    try:
                        batch.append(q.get_nowait())
                    except queue.Empty:
                        break
                yield "".join(f"data: {m}\n\n" for m in batch)
        except GeneratorExit:
            pass
        finally:
            remove_subscriber(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@api_bp.route("/logs/history", methods=["GET"])
def log_history_list_api():
    files = list_history_logs()
    items = [{"filename": f} for f in files]
    return jsonify({"ok": True, "items": items})

@api_bp.route("/logs/history/<filename>", methods=["GET"])
def log_history_get_api(filename):
    lines = get_history_log(filename)
    if lines:
        return jsonify({"ok": True, "lines": lines})
    return jsonify({"ok": False, "error": "Not found"}), 404

@api_bp.route("/logs/history/<filename>", methods=["DELETE"])
def log_history_delete_api(filename):
    ok = delete_history_log(filename)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Failed to delete"}), 500

@api_bp.route("/logs/current", methods=["DELETE"])
def log_current_delete_api():
    ok = clear_current_log_session()
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Failed to delete"}), 500

@api_bp.route("/accounts", methods=["GET"])
def list_accounts_api():
    accounts = parse_accounts()
    return jsonify(accounts)

@api_bp.route("/accounts", methods=["DELETE"])
def delete_accounts_api():
    body = request.get_json(force=True) or {}
    indices = set(body.get("indices", []))
    mode = body.get("mode", "selected")

    accounts = parse_accounts()
    if mode == "all":
        write_accounts([])
        for acc in accounts:
            delete_token_file(acc.get("email", ""))
        return jsonify({"ok": True, "deleted": len(accounts)})

    to_delete = [a for a in accounts if a["index"] in indices]
    for acc in to_delete:
        delete_token_file(acc.get("email", ""))

    remaining = [a for a in accounts if a["index"] not in indices]
    write_accounts([a for a in remaining if a.get("oauth_status") != "token-only"])
    return jsonify({"ok": True, "deleted": len(to_delete)})

@api_bp.route("/export", methods=["POST"])
def export_oauth_api():
    body = request.get_json(force=True) or {}
    mode = body.get("mode", "all")
    indices = body.get("indices", [])
    
    buf, filename_or_err = export_tokens_zip(mode, indices)
    if buf is None:
        return jsonify({"error": filename_or_err}), 404
        
    from flask import send_file
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename_or_err
    )

@api_bp.route("/dashboard-summary", methods=["GET"])
def dashboard_summary_api():
    accounts = parse_accounts()
    token_stats = count_token_stats()
    task_status = get_task_status()
    
    oauth_ok = 0
    token_only = 0
    oauth_error = 0

    for account in accounts:
        status = (account.get("oauth_status") or "").strip()
        if status == "token-only":
            token_only += 1
        elif "ok" in status:
            oauth_ok += 1
        elif status:
            oauth_error += 1

    return jsonify({
        "ok": True,
        "accounts": {
            "total": len(accounts),
            "oauth_ok": oauth_ok,
            "token_only": token_only,
            "oauth_error": oauth_error,
        },
        "tokens": token_stats,
        "register": task_status,
    })

# ─── SingBox 代理 ───

@api_bp.route("/singbox/parse", methods=["POST"])
def singbox_parse_api():
    body = request.get_json(force=True) or {}
    url = (body.get("url") or "").strip()
    proxy = (body.get("proxy") or "").strip() or None
    if not url:
        return jsonify({"ok": False, "error": "缺少订阅地址"}), 400
    try:
        details = inspect_subscription(url, proxy=proxy)
        cached_payload = save_cached_subscription(url, details)
        names = [n["tag"] for n in details["nodes"]]
        return jsonify({
            "ok": True,
            "cached_at": cached_payload["cached_at"],
            "count": len(names),
            "content_type": details.get("content_type", ""),
            "nodes": names,
            "payload_type": details["payload_type"],
            "profile_name": details["profile_name"],
            "source_type": details["source_type"],
            "warnings": details["warnings"],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api_bp.route("/singbox/start", methods=["POST"])
def singbox_start_api():
    body = request.get_json(force=True) or {}
    url = (body.get("url") or "").strip()
    proxy = (body.get("proxy") or "").strip() or None
    listen_port = safe_int(body.get("listen_port"), 10810, minimum=1)
    api_port = safe_int(body.get("api_port"), 9090, minimum=1)
    if not url:
        return jsonify({"ok": False, "error": "缺少订阅地址"}), 400
    try:
        cached = load_cached_subscription(url)
        cache_hit = cached is not None
        if not cached:
            details = inspect_subscription(url, proxy=proxy)
            cached = save_cached_subscription(url, details)
        nodes = get_cached_node_pool(url)
        if not nodes:
            return jsonify({"ok": False, "error": "缓存中没有可用节点，请先重新解析或执行节点测试"}), 400
        start_singbox(nodes, listen_port=listen_port, api_port=api_port)
        return jsonify({
            "ok": True,
            "count": len(nodes),
            "cached": cache_hit,
            "pool_only": bool((cached.get("health_check") or {}).get("available_tags")),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@api_bp.route("/singbox/stop", methods=["POST"])
def singbox_stop_api():
    stop_singbox()
    return jsonify({"ok": True})

@api_bp.route("/singbox/status", methods=["GET"])
def singbox_status_api():
    url = request.args.get("url", "").strip()
    nodes = []
    results = []
    if url:
        try:
            from src.services.singbox_cache import load_cached_subscription
            payload = load_cached_subscription(url)
            if payload:
                nodes = [item.get("tag") for item in payload.get("nodes", []) if isinstance(item, dict) and item.get("tag")]
                results = payload.get("health_check", {}).get("results", [])
        except Exception:
            pass
    return jsonify({
        "ok": True,
        **get_singbox_status(),
        "cached_nodes": nodes,
        "test_results": results
    })

@api_bp.route("/singbox/test", methods=["POST"])
def singbox_test_api():
    body = request.get_json(force=True) or {}
    url = (body.get("url") or "").strip()
    test_url = (body.get("test_url") or "").strip() or None
    if not url:
        return jsonify({"ok": False, "error": "缺少订阅地址"}), 400

    status = get_singbox_status()
    if not status.get("running"):
        return jsonify({"ok": False, "error": "SingBox 未运行，无法执行节点测试"}), 409

    cached = load_cached_subscription(url)
    if not cached:
        return jsonify({"ok": False, "error": "请先解析订阅并写入本地缓存"}), 400

    full_nodes = cached["nodes"]
    if not full_nodes:
        return jsonify({"ok": False, "error": "本地缓存中没有可测试节点"}), 400

    try:
        runtime_tags = get_runtime_node_names()
        full_tags = [node.get("tag") for node in full_nodes if node.get("tag")]
        if not _same_node_tags(runtime_tags, full_tags):
            start_singbox(full_nodes, listen_port=status["listen_port"], api_port=status["api_port"])
            runtime_tags = full_tags
        test_result = batch_test_nodes(full_nodes, test_url=test_url)
        cache_payload = update_cached_node_health(url, test_result["results"], test_result["test_url"])
        available_nodes = test_result["available_nodes"]
        available_tags = [node.get("tag") for node in available_nodes if node.get("tag")]
        if available_nodes:
            if not _same_node_tags(runtime_tags, available_tags):
                start_singbox(available_nodes, listen_port=status["listen_port"], api_port=status["api_port"])
        elif not _same_node_tags(runtime_tags, full_tags):
            start_singbox(full_nodes, listen_port=status["listen_port"], api_port=status["api_port"])

        return jsonify({
            "ok": True,
            "available": len(available_nodes),
            "best_node": test_result["best_node"],
            "results": test_result["results"],
            "test_url": test_result["test_url"],
            "tested_at": cache_payload["health_check"]["tested_at"],
            "total": len(full_nodes),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
