import os
import queue
import threading
import json
from datetime import datetime

# ── SSE log broadcast ──────────────────────────────────────
_log_subscribers: list[queue.Queue] = []
_log_lock = threading.Lock()
_log_queue = queue.Queue(maxsize=50000)
_current_log_lock = threading.Lock()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# 支持同时记录到文件，保存历史记录
_current_log_file = None
_current_log_buffer = []

def init_logger():
    os.makedirs(LOGS_DIR, exist_ok=True)
    threading.Thread(target=_log_dispatcher, daemon=True, name="log-dispatcher").start()

def start_log_session(prefix="task"):
    global _current_log_file, _current_log_buffer
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with _current_log_lock:
        _current_log_file = os.path.join(LOGS_DIR, f"{prefix}_{ts}.json")
        _current_log_buffer = []

def complete_log_session():
    global _current_log_file, _current_log_buffer
    log_file = None
    log_lines = []
    with _current_log_lock:
        log_file = _current_log_file
        log_lines = list(_current_log_buffer)
        _current_log_file = None
        _current_log_buffer = []
    if log_file:
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_lines, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def clear_current_log_session():
    global _current_log_buffer
    with _current_log_lock:
        _current_log_buffer = []
    return True

def broadcast_log(line: str):
    """高并发安全：只做一次 queue.put，不持有 _log_lock"""
    # 记录到当前活跃的历史记录中
    with _current_log_lock:
        if _current_log_file is not None:
            _current_log_buffer.append(line)

    try:
        _log_queue.put_nowait(line)
    except queue.Full:
        try:
            _log_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            _log_queue.put_nowait(line)
        except queue.Full:
            pass

def _log_dispatcher():
    """专用分发线程：从中央队列批量读取，分发给所有 SSE 订阅者"""
    while True:
        try:
            msg = _log_queue.get(timeout=1)
        except queue.Empty:
            continue
        batch = [msg]
        while len(batch) < 500:
            try:
                batch.append(_log_queue.get_nowait())
            except queue.Empty:
                break
        with _log_lock:
            for q in _log_subscribers:
                for m in batch:
                    if q.full():
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            pass
                    try:
                        q.put_nowait(m)
                    except queue.Full:
                        pass

def register_subscriber(q):
    with _log_lock:
        _log_subscribers.append(q)

def remove_subscriber(q):
    with _log_lock:
        if q in _log_subscribers:
            _log_subscribers.remove(q)

def list_history_logs():
    if not os.path.exists(LOGS_DIR):
        return []
    files = [f for f in os.listdir(LOGS_DIR) if f.endswith(".json")]
    files.sort(reverse=True)
    return files

def get_history_log(filename):
    path = os.path.join(LOGS_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def delete_history_log(filename):
    if filename == "all":
        # 删除所有
        for f in list_history_logs():
            try:
                os.remove(os.path.join(LOGS_DIR, f))
            except Exception:
                pass
        return True
    path = os.path.join(LOGS_DIR, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except Exception:
            return False
    return False
