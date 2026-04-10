import os
import io
import json
import zipfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "registered_accounts.txt")
TOKEN_DIR = os.path.join(BASE_DIR, "codex_tokens")


def _format_registered_at(filepath):
    try:
        timestamp = os.path.getctime(filepath)
    except OSError:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _list_token_entries():
    entries = []
    if not os.path.isdir(TOKEN_DIR):
        return entries
    for fname in sorted(os.listdir(TOKEN_DIR)):
        fpath = os.path.join(TOKEN_DIR, fname)
        if not fname.endswith(".json") or not os.path.isfile(fpath):
            continue
        entries.append({
            "display_name": fname[:-5],
            "name": fname[:-5].lower(),
            "registered_at": _format_registered_at(fpath),
        })
    return entries


def _lookup_registered_at(email, token_entries):
    email_key = (email or "").lower()
    if not email_key:
        return ""
    for entry in token_entries:
        if email_key == entry["name"] or email_key in entry["name"]:
            return entry["registered_at"]
    return ""

def is_codex_token(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("type") == "codex"
    except Exception:
        return False

def parse_accounts():
    accounts = []
    seen_emails = set()
    token_entries = _list_token_entries()

    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("----")
                email = parts[0] if len(parts) > 0 else ""
                acc = {
                    "index": i,
                    "email": email,
                    "password": parts[1] if len(parts) > 1 else "",
                    "email_password": parts[2] if len(parts) > 2 else "",
                    "oauth_status": parts[3] if len(parts) > 3 else "",
                    "registered_at": _lookup_registered_at(email, token_entries),
                    "raw": line,
                }
                accounts.append(acc)
                if email:
                    seen_emails.add(email.lower())

    if os.path.isdir(TOKEN_DIR):
        for entry in token_entries:
            name = entry["display_name"]
            name_key = entry["name"]
            if any(name_key in e for e in seen_emails):
                continue
            idx = len(accounts)
            accounts.append({
                "index": idx,
                "email": name,
                "password": "",
                "email_password": "",
                "oauth_status": "token-only",
                "registered_at": entry["registered_at"],
                "raw": name,
            })
    return accounts

def write_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        for acc in accounts:
            f.write(acc["raw"] + "\n")

def delete_token_file(email):
    if not email:
        return
    fname = f"{email}.json"
    fpath = os.path.join(TOKEN_DIR, fname)
    try:
        if os.path.isfile(fpath):
            os.remove(fpath)
    except Exception:
        pass

def iter_codex_token_files():
    if not os.path.isdir(TOKEN_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(TOKEN_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(TOKEN_DIR, fname)
        if os.path.isfile(fpath) and is_codex_token(fpath):
            files.append(fpath)
    return files

def count_token_stats():
    stats = {"total": 0, "active": 0, "disabled": 0}
    for fpath in iter_codex_token_files():
        stats["total"] += 1
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("disabled"):
                stats["disabled"] += 1
            else:
                stats["active"] += 1
        except Exception:
            stats["active"] += 1
    return stats

def export_tokens_zip(mode, indices):
    if mode == "selected":
        accounts = parse_accounts()
        target_emails = {a["email"] for a in accounts if a["index"] in set(indices)}
    else:
        target_emails = None
        
    if not os.path.isdir(TOKEN_DIR):
        return None, "codex_tokens 目录不存在"

    buf = io.BytesIO()
    exported = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(TOKEN_DIR)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(TOKEN_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as tf:
                    content = tf.read()
            except Exception:
                continue

            if target_emails is not None:
                stem = fname[:-5]
                matched = any(em in stem or em in content for em in target_emails)
                if not matched:
                    continue

            zf.writestr(fname, content)
            exported += 1

    if exported == 0:
        return None, "没有找到匹配的 Token 文件"
    
    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return buf, f"codex_tokens_{ts}.zip"
