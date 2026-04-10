# Codex Register

ChatGPT / OpenAI Codex 批量账号注册与管理工具。纯协议实现，无需浏览器（注册流程），可选 Playwright 支持 Turnstile 验证。

> 邮箱 API 购买地址：https://royp.online/

---

## 功能特性

### 核心功能
- **批量自动注册** — 纯 HTTP 协议完成全流程：创建邮箱 → 注册 → OTP 验证 → 账号创建 → OAuth Token
- **Codex OAuth** — PKCE 流程自动交换 Access Token / Refresh Token，支持自动刷新
- **多邮箱提供商** — DuckMail / Cloudflare Mail Worker / YYDS Mail / **MailAPI.ICU（含批量导入）**
- **Sentinel Token 双引擎** — 纯 Python PoW + Playwright Turnstile，智能策略自动切换
- **代理支持** — 固定代理 / SingBox 动态轮换，支持 `user:pass@host:port` 认证

### Web 管理面板

基于 Vue 3 + Tailwind CSS 的可视化控制台，访问 `http://127.0.0.1:5001`：

| 页面 | 功能 |
|------|------|
| 仪表盘 | 注册任务状态、账号统计图表 |
| 注册任务 | 启动/停止批量注册、设置数量/并发数/代理、SSE 实时日志 |
| 已注册账号库 | 查看所有已注册账号（邮箱/OAuth状态/注册时间）、导出 ZIP 包、删除 |
| 邮箱设置 | 切换邮箱提供商（4种）、配置参数、**批量导入 MailAPI.ICU 邮箱池** |
| 网络代理 | 固定代理地址配置 / SingBox 订阅一键导入与节点管理 |
| OAuth 授权 | 查看 OAuth 参数、上传 Codex Token |

---

## 快速开始

### 第 1 步：安装 Python 依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# Windows 激活
.\venv\Scripts\Activate.ps1

# Linux / macOS 激活
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

> 需要 Python 3.7+

### 第 2 步：安装 Playwright（推荐）

Playwright 用于获取带 Turnstile 验证的 Sentinel Token，**显著提升注册成功率**：

```bash
pip install playwright>=1.40.0
playwright install chromium
```

> 不安装也可运行，会回退到纯 HTTP PoW 模式（可能被 OpenAI 拒绝）。

### 第 3 步：构建前端

`dist/` 目录已包含预构建产物。如需修改前端界面：

```bash
cd frontend
npm install
npm run build
cd ..
```

产物自动输出到 `dist/` 目录。

### 第 4 步：配置 config.json

编辑项目根目录的 `config.json`：

#### 必填：选择邮箱提供商并配置

**方式 A — 使用 MailAPI.ICU（推荐）**

```jsonc
{
  "mail_provider": "mailapi_icu",        // 固定值
  "mailapi_icu_bulk": [                   // 批量邮箱池（注册时自动轮换）
    {
      "email": "your1@hotmail.com",
      "api_url": "https://mailapi.icu/key?type=html&orderNo=你的订单号"
    },
    {
      "email": "your2@hotmail.com",
      "api_url": "https://mailapi.icu/key?type=html&orderNo=你的订单号2"
    }
  ]
}
```

也可以在 Web 面板 → **邮箱设置** → 批量导入文本框中粘贴：
```
邮箱地址----取件API地址
user1@hotmail.com----https://mailapi.icu/key?type=html&orderNo=xxxxxxxx
user2@hotmail.com----https://mailapi.icu?key?type=html&orderNo=yyyyyyyy
```

**方式 B — 单个 ICU 邮箱**
```jsonc
{
  "mail_provider": "mailapi_icu",
  "mailapi_icu_email": "your@hotmail.com",
  "mailapi_icu_order_no": "你的订单号"
}
```

**方式 C — 其他提供商**

| mail_provider 值 | 需要填写的字段 |
|------------------|--------------|
| `"duckmail"` | `duckmail_api_base`, `duckmail_domain`, `duckmail_bearer` |
| `"cloudflare"` | `cf_mail_api_base`, `cf_mail_domain`, `cf_mail_admin_password` |
| `"yyds_mail"` | `yyds_mail_api_base`, `yyds_mail_api_key`, `yyds_mail_domain` |

#### 必填：配置代理

**固定代理（最常用）：**
```jsonc
{
  "proxy_mode": "fixed",
  "proxy": "http://用户名:密码@代理地址:端口"
}
// 例如: "http://user-sub:xxx@proxy.haiwaiip.net:1463"
```

支持的格式：
- `http://user:pass@host:port` — HTTP 代理 + 用户名密码认证
- `socks5://user:pass@host:port` — SOCKS5 代理
- `socks5h://...` — SOCKS5 远程 DNS 解析

**SingBox 动态轮换（可选）：**
```jsonc
{
  "proxy_mode": "singbox",          // 或保持 fixed 但 proxy 填 singbox://
  "singbox_enabled": true,
  "singbox_subscription": "https://你的订阅链接"   // Clash/Mihomo 格式订阅
}
```
然后在 Web 面板 → **网络代理** 中点击「解析订阅」即可使用。支持 vmess/vless/trojan/shadowsocks/hysterias 协议。

#### 可选：OAuth 配置

```jsonc
{
  "enable_oauth": true,              // 注册完成后自动换取 Token
  "oauth_required": true             // 是否要求必须成功获取 OAuth
}
```

一般无需修改默认值。

### 第 5 步：启动服务

```bash
# Windows
python app.py

# Linux / macOS（一键脚本）
chmod +x start.sh
./start.sh
```

启动后访问：**http://127.0.0.1:5001**

---

## 使用教程

### 注册账号

1. 打开 Web 面板 `http://127.0.0.1:5001`
2. 进入 **注册任务** 页面
3. 设置参数：
   - **注册数量** — 要注册几个账号
   - **并发数** — 同时跑几个线程（建议 1-5）
   - **代理** — 可覆盖全局代理（留空则用 config.json 的配置）
4. 点击 **开始任务**
5. 观察实时日志输出（SSE 推送，无需刷新）
6. 注册成功的账号自动保存到 `codex_tokens/` 目录和 `ak.txt`/`rk.txt`

### 管理已注册账号

进入 **已注册账号库** 页面：
- 查看所有账号的邮箱、密码、OAuth 状态、注册时间
- **导出** — 选中或全部导出为 ZIP 包（含 Token JSON）
- **删除** — 选中或全部删除账号数据

### 配置邮箱

进入 **邮箱设置** 页面：
1. 选择 **邮件服务商**
2. 填写对应参数
3. 如果是 MailAPI.ICU，在底部 **批量导入** 文本框粘贴格式化数据
4. 点 **保存**

### 配置代理

进入 **网络代理** 页面：
- **固定代理模式**：填写代理地址，点保存
- **SingBox 模式**：粘贴订阅链接 → 解析订阅 → 测试节点 → 启动

---

## 注册流程详解

```
┌─────────────────────────────────────────────────────┐
│                  V3 注册流程                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Step 1  访问 chatgpt.com 首页 → 建立 session        │
│    ↓                                                 │
│  Step 2  获取 CSRF token                             │
│    ↓                                                 │
│  Step 3  POST signin (login_hint=email)              │
│    ↓                                                 │
│  Step 4  GET authorize → 重定向到密码页                │
│    ↓                                                 │
│  Step 5  POST register (Sentinel+Turnstile) → 设置密码 │
│    ↓                                                 │
│  Step 6  发送 OTP → 轮询邮箱验证码 → validate_otp     │
│    ↓                                                 │
│  Step 7  POST create_account (Sentinel+Turnstile)     │
│    ↓                                                 │
│  Step 8  [可选] 绕过 add-phone (3 种策略)             │
│    ↓                                                 │
│  Step 9  Callback → PKCE OAuth Token 交换            │
│    ↓                                                 │
│  ✅ 保存: codex_tokens/{email}.json + ak.txt + rk.txt │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Sentinel Token 引擎

| 模式 | 原理 | 适用场景 | Turnstile |
|------|------|----------|-----------|
| **纯 HTTP PoW** | Python 实现 Proof-of-Work | 读操作（authorize 等） | 无 |
| **Playwright** | Chromium 加载真实 SentinelSDK JS | 写操作（register/create_account） | 有 |

智能策略：读操作 HTTP 优先（快），写操作 Playwright 优先（需要 Turnstile t 字段），失败自动回退。

Playwright 代理支持：自动解析 `user:pass@host:port` 格式为 `{server, username, password}`。

---

## 项目结构

```
.
├── app.py                    # Flask 后端入口
├── config_loader.py          # 核心注册逻辑
├── config.json               # 运行配置（需自行填写）
├── playwright_sentinel.py    # Playwright Sentinel + Turnstile
├── sentinel_sdk_version.py   # Sentinel SDK 版本动态探测
├── requirements.txt          # Python 依赖
├── start.sh                  # Linux/macOS 一键启动脚本
├── core/                     # sing-box 可执行文件
├── dist/                     # 前端构建产物（后端托管）
├── frontend/                 # 前端源码
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   ├── components/       # shadcn/ui 组件库
│   │   ├── lib/api.ts        # API 封装
│   │   ├── router/index.ts   # 路由配置
│   │   └── layouts/AppLayout.vue  # 主布局（侧边栏+横幅）
│   └── vite.config.ts        # Vite 构建配置
├── src/
│   ├── routes/api.py         # Flask REST API
│   └── services/
│       ├── task.py           # 注册任务管理（进程池）
│       ├── singbox.py        # SingBox 代理管理
│       ├── singbox_cache.py  # 节点健康缓存
│       └── logger.py         # SSE 日志广播
├── codex_tokens/             # 输出的 Token JSON（每账号一个文件）
├── ak.txt                    # Access Token 汇总（每行一个）
├── rk.txt                    # Refresh Token 汇总（每行一个）
├── registered_accounts.csv   # 已注册账号列表
└── logs/                     # 运行日志
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.7+ / Flask / curl_cffi (TLS 指纹) |
| 前端 | Vue 3 / Vite / TypeScript / Tailwind CSS |
| UI 组件 | shadcn/ui (Radix Vue) |
| 图表 | @unovis/vue |
| 浏览器自动化 | Playwright (Chromium) |
| 代理 | sing-box (Clash/Mihomo 订阅) |
| 实时通信 | SSE (Server-Sent Events) |

## Python 依赖

```
flask>=2.3.0          # Web 框架
requests>=2.28.0      # HTTP 客户端
curl_cffi>=0.5.0      # TLS 指纹伪装（核心依赖）
PyYAML>=6.0.0         # YAML 解析（订阅格式）
PySocks>=1.7.0        # SOCKS5 代理
playwright>=1.40.0    # Turnstile 挑战（可选但推荐）
```

## 注意事项

- `config.json` 需要填写真实的邮箱和代理信息才能运行
- `dist/` 已包含预构建的前端产物，可直接启动使用
- 修改前端后需执行 `cd frontend && npm run build`
- Playwright 的 Turnstile token 对注册成功率有显著影响，建议安装
- MailAPI.ICU 批量池中的邮箱会被轮换使用，注册失败不会消耗同一邮箱的次数
- 代理格式务必正确：`http://user:pass@host:port` 或 `socks5://user:pass@host:port`

## License

MIT
