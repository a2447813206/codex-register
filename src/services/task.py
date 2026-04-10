import queue
import threading
import multiprocessing
import os

from src.services.logger import broadcast_log, start_log_session, complete_log_session
from src.utils.account import TOKEN_DIR

_task_lock = threading.Lock()
_task_running = False
_task_progress = {"total": 0, "done": 0, "success": 0, "fail": 0}

_task_process = None
_task_log_queue = None


def _log_singbox_runtime(context, proxy):
    if proxy != "singbox://":
        return
    try:
        from src.services.singbox import format_runtime_node_log
        broadcast_log(format_runtime_node_log(context))
    except Exception as exc:
        broadcast_log(f"[SingBox] {context}: 节点状态读取失败 - {exc}")

def _task_subprocess(log_q, count, workers, proxy):
    import sys, io

    class _QueueWriter(io.TextIOBase):
        def __init__(self, real):
            self._real = real
        def write(self, s):
            if s and s.strip():
                for line in s.rstrip("\n\r").split("\n"):
                    if line.strip():
                        try:
                            log_q.put_nowait(line)
                        except:
                            pass
            return self._real.write(s)
        def flush(self):
            return self._real.flush()

    sys.stdout = _QueueWriter(sys.__stdout__)
    try:
        import importlib
        import config_loader
        importlib.reload(config_loader)
        config_loader.run_batch(
            total_accounts=count,
            output_file="registered_accounts.txt",
            max_workers=workers,
            proxy=proxy,
        )
    except Exception as e:
        print(f"[ERROR] 任务异常: {e}")

def _log_reader(log_q):
    global _task_running
    while True:
        try:
            msg = log_q.get(timeout=1)
            broadcast_log(msg)
        except queue.Empty:
            if _task_process is None or not _task_process.is_alive():
                break
    with _task_lock:
        _task_running = False
    broadcast_log("__TASK_DONE__")
    complete_log_session()

def start_registration_task(count, workers, proxy):
    global _task_running, _task_process, _task_log_queue, _task_progress
    with _task_lock:
        if _task_running:
            return False, "任务正在运行中"

    _task_progress = {"total": count, "done": 0, "success": 0, "fail": 0}
    _task_log_queue = multiprocessing.Queue(maxsize=1000)
    _log_singbox_runtime("注册启动前", proxy)
    _task_process = multiprocessing.Process(
        target=_task_subprocess,
        args=(_task_log_queue, count, workers, proxy),
        daemon=True,
    )
    _task_running = True
    start_log_session("register")
    _task_process.start()
    threading.Thread(target=_log_reader, args=(_task_log_queue,), daemon=True).start()
    return True, None

def stop_registration_task():
    global _task_running, _task_process
    if _task_process and _task_process.is_alive():
        _task_process.kill()
        _task_process.join(timeout=2)
        _task_process = None
    with _task_lock:
        _task_running = False
    broadcast_log("⚠️ 任务已停止")
    broadcast_log("__TASK_DONE__")
    complete_log_session()

def get_task_status():
    return {
        "running": _task_running,
        "progress": _task_progress,
    }
