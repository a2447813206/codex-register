"""
构建脱敏分享快照

生成一个干净的项目副本，用于分享给他人排查问题：
  - 不含 venv / node_modules / __pycache__ / har / herosms / .claude 等
  - config.json 使用默认模板，所有凭据字段置空
  - 自动生成 README.md
  - 包含 frontend 源码（不含 node_modules）

用法:
    python scripts/build_share_snapshot.py
"""

import json
import shutil
import textwrap
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARE_DIR = ROOT / "share"

# ── 需要复制的目录 ──────────────────────────────────────────

COPY_DIRS = (
    "core",
    "dist",
    "frontend",
    "scripts",
    "src",
)

# ── 需要复制的根目录文件 ────────────────────────────────────

COPY_FILES = (
    "app.py",
    "config_loader.py",
    "herosms_client.py",
    "notifier.py",
    "playwright_sentinel.py",
    "sentinel_sdk_version.py",
    "requirements.txt",
    "start.sh",
)

# ── 需要创建的空目录 ────────────────────────────────────────

EMPTY_DIRS = (
    "codex_tokens",
    "logs",
)

# ── 复制时全局忽略的模式 ────────────────────────────────────

IGNORE_PATTERNS = (
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.log",
    ".vscode",
    ".claude",
    ".git",
    ".gitignore",
    ".sentinel_sdk_version.json",
    "node_modules",
    "venv",
    ".venv",
    "har",
    "herosms",
)

# ── 脱敏后的默认配置 ────────────────────────────────────────

DEFAULT_CONFIG = {
    "mail_provider": "cloudflare",
    "cf_mail_api_base": "",
    "cf_mail_domain": "",
    "cf_mail_admin_password": "",
    "duckmail_api_base": "",
    "duckmail_domain": "",
    "duckmail_bearer": "",
    "yyds_mail_api_base": "",
    "yyds_mail_api_key": "",
    "yyds_mail_domain": "",
    "yyds_mail_domains": [],
    "proxy": "",
    "proxy_mode": "fixed",
    "singbox_enabled": False,
    "singbox_listen_port": 10810,
    "singbox_api_port": 9090,
    "singbox_sub": "",
    "singbox_subscription": "",
    "enable_oauth": True,
    "oauth_required": True,
    "oauth_issuer": "https://auth.openai.com",
    "oauth_client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
    "oauth_redirect_uri": "http://localhost:1455/auth/callback",
    "codex_token": "",
    "ak_file": "ak.txt",
    "rk_file": "rk.txt",
    "token_json_dir": "codex_tokens",
    "SUB2API_URL": "",
    "SUB2API_TOKEN": "",
    "cpa_auto_sync": False,
    "cpa_use_proxy": False,
    "keepalive_enabled": False,
    "keepalive_interval": 3600,
    "keepalive_target_count": 20,
    "keepalive_probe_enabled": False,
    "keepalive_probe_usage": False,
    "keepalive_max_probe": 150,
    "keepalive_probe_workers": 5,
    "keepalive_register_workers": 3,
    "keepalive_quota_action": "disable",
    "keepalive_delete_401": True,
    "keepalive_auto_reenable": True,
    "webhook_enabled": False,
    "webhook_type": [],
    "webhook_tg_token": "",
    "webhook_tg_chat_id": "",
    "webhook_ding_url": "",
    "webhook_ding_secret": "",
    "webhook_wxwork_url": "",
    "teams": [],
    "team_auth_token": "",
    "team_session_token": "",
    "ddg_token": "",
    "ddg_mail_url": "",
    "herosms_api_key": "",
    "herosms_service": "dr",
    "herosms_country": 187,
    "herosms_max_price": -1,
}

# ── 占位空文件 ──────────────────────────────────────────────

TEXT_FILES = {
    "ak.txt": "",
    "rk.txt": "",
    "registered_accounts.txt": "",
    "registered_accounts.csv": "email,password,duckmail_password,oauth_status,timestamp\n",
}

JSON_FILES = {
    "config.json": DEFAULT_CONFIG,
    "invite_tracker.json": {},
    "keepalive_history.json": [],
    "singbox_nodes_cache.json": {},
}


# ── 工具函数 ────────────────────────────────────────────────

def reset_share_dir() -> None:
    if SHARE_DIR.exists():
        shutil.rmtree(SHARE_DIR)
    SHARE_DIR.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        print(f"  [跳过] 目录不存在: {src.name}/")
        return
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
    )
    print(f"  [复制] {src.name}/")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    content = json.dumps(data, indent=4, ensure_ascii=False) + "\n"
    write_text(path, content)


# ── 主要步骤 ────────────────────────────────────────────────

def copy_project_snapshot() -> None:
    print("复制项目文件...")
    for name in COPY_DIRS:
        copy_tree(ROOT / name, SHARE_DIR / name)

    for name in COPY_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, SHARE_DIR / name)
            print(f"  [复制] {name}")
        else:
            print(f"  [跳过] 文件不存在: {name}")


def write_runtime_placeholders() -> None:
    print("写入占位文件...")
    for name, content in TEXT_FILES.items():
        write_text(SHARE_DIR / name, content)

    for name, data in JSON_FILES.items():
        write_json(SHARE_DIR / name, data)

    for name in EMPTY_DIRS:
        (SHARE_DIR / name).mkdir(parents=True, exist_ok=True)


def generate_readme() -> None:
    """根据项目结构生成脱敏的 README"""
    readme = textwrap.dedent("""\
    # Codex Register

    ChatGPT / Codex 批量账号注册与管理工具。

    ## 功能概览

    - **批量注册** — 自动创建 ChatGPT 账号（邮箱注册 → 邮箱 OTP 验证 → 账号创建）
    - **Codex OAuth** — 注册后自动获取 Codex API Token（access_token / refresh_token）
    - **Team 邀请** — 注册后自动邀请加入指定 Team
    - **自动保活** — 定时检测账号可用性，自动补号
    - **手机验证 (HeroSMS)** — 遇到 add-phone 要求时自动接码验证
    - **Sentinel PoW** — 纯协议 + Playwright 双模式生成 Sentinel Token
    - **SingBox 代理** — 内置 sing-box 代理管理，支持节点轮换与健康检测
    - **Webhook 通知** — 支持 Telegram / 钉钉 / 企业微信推送注册结果
    - **CPA 同步** — 将 Token 推送至外部 API 服务
    - **Web 管理面板** — 基于 Vue 3 的可视化控制台

    ## 项目结构

    ```
    .
    ├── app.py                    # Flask 后端入口
    ├── config_loader.py          # 核心注册逻辑
    ├── config.json               # 运行配置（需自行填写）
    ├── herosms_client.py         # HeroSMS 接码平台客户端
    ├── playwright_sentinel.py    # Playwright Sentinel Token 生成器
    ├── sentinel_sdk_version.py   # Sentinel SDK 版本动态探测
    ├── notifier.py               # Webhook 通知模块
    ├── requirements.txt          # Python 依赖
    ├── start.sh                  # Linux/macOS 启动脚本
    ├── core/                     # sing-box 可执行文件
    ├── dist/                     # 前端构建产物（后端直接托管）
    ├── frontend/                 # 前端源码（Vue 3 + Vite + Tailwind）
    │   ├── src/
    │   │   ├── views/            # 页面组件
    │   │   ├── components/       # UI 组件库
    │   │   ├── lib/api.ts        # API 调用封装
    │   │   ├── store/            # Pinia 状态管理
    │   │   └── router/           # 路由配置
    │   └── package.json
    ├── src/
    │   ├── routes/api.py         # Flask API 路由
    │   ├── services/             # 业务服务（任务、保活、SingBox 等）
    │   └── utils/                # 工具函数
    ├── codex_tokens/             # 输出的 Token JSON 文件
    ├── logs/                     # 注册日志
    └── scripts/                  # 辅助脚本
    ```

    ## 快速开始

    ### 1. 安装 Python 依赖

    ```bash
    python -m venv venv

    # Windows
    .\\venv\\Scripts\\Activate.ps1

    # Linux / macOS
    source venv/bin/activate

    pip install -r requirements.txt
    ```

    ### 2. 安装 Playwright（可选，用于 Sentinel Token）

    ```bash
    pip install playwright
    playwright install chromium
    ```

    ### 3. 安装前端依赖并构建（仅修改前端时需要）

    ```bash
    cd frontend
    npm install
    npm run build
    cd ..
    ```

    构建产物输出到 `dist/`，后端启动时自动加载。

    ### 4. 配置

    编辑 `config.json`，填写必要的配置项：

    | 配置项 | 说明 | 示例 |
    |--------|------|------|
    | `mail_provider` | 邮箱提供商 (`cloudflare` / `duckmail` / `yyds_mail`) | `"cloudflare"` |
    | `cf_mail_api_base` | Cloudflare 邮箱 API 地址 | `"https://mail.example.com/"` |
    | `cf_mail_domain` | Cloudflare 邮箱域名 | `"example.com"` |
    | `cf_mail_admin_password` | Cloudflare 邮箱管理密码 | |
    | `proxy` | 代理地址 | `"socks5://127.0.0.1:10808"` |
    | `proxy_mode` | 代理模式 (`fixed` / `singbox`) | `"fixed"` |
    | `enable_oauth` | 是否获取 Codex OAuth Token | `true` |
    | `herosms_api_key` | HeroSMS 接码平台 API Key（可选） | |
    | `herosms_service` | HeroSMS 服务代码 | `"dr"` (OpenAI) |
    | `herosms_country` | HeroSMS 国家 ID | `187` (USA) |
    | `herosms_max_price` | 最高单价（-1 不限制） | `-1` |
    | `webhook_enabled` | 是否启用 Webhook 通知 | `false` |
    | `teams` | Team 配置列表 | `[]` |

    更多配置项请参考 Web 管理面板中的设置页面。

    ### 5. 启动

    ```bash
    python app.py
    ```

    默认访问地址：`http://127.0.0.1:5001`

    ## 注册流程

    ```
    1. 创建临时邮箱
    2. 访问 ChatGPT 首页 → 获取 CSRF → Signin（login_hint）
    3. Authorize 重定向到 /create-account/password
    4. Sentinel Token（Playwright 含 Turnstile）→ 设置密码
    5. 发送邮箱 OTP → 等待验证码 → 验证
    6. Sentinel Token → 创建账号
    7. 如遇 add-phone → 先尝试跳过 → 失败则 HeroSMS 接码
    8. Codex OAuth Token 交换
    9. 保存结果（账号库 + Token 文件）
    ```

    ## 技术栈

    | 层 | 技术 |
    |----|------|
    | 后端 | Python 3.10+ / Flask / curl_cffi |
    | 前端 | Vue 3 / Vite / Tailwind CSS / Radix Vue |
    | 浏览器自动化 | Playwright（Sentinel Token 生成） |
    | 代理 | sing-box（内置管理，Clash API 控制） |
    | 接码平台 | HeroSMS（可选） |

    ## 注意事项

    - 本快照为脱敏版本，`config.json` 中所有凭据已置空，需自行配置。
    - `dist/` 目录已包含预构建的前端产物，无需额外构建即可启动。
    - 如需修改前端，请在 `frontend/` 中执行 `npm install && npm run build`。
    """)

    write_text(SHARE_DIR / "README.md", readme)
    print("  [生成] README.md")


# ── 入口 ────────────────────────────────────────────────────

def main() -> None:
    print(f"目标目录: {SHARE_DIR}\n")
    reset_share_dir()
    copy_project_snapshot()
    write_runtime_placeholders()
    generate_readme()

    # 统计
    total_files = sum(1 for _ in SHARE_DIR.rglob("*") if _.is_file())
    print(f"\n完成! 共 {total_files} 个文件")
    print(f"路径: {SHARE_DIR}")


if __name__ == "__main__":
    main()
