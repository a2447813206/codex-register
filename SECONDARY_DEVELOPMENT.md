# Codex Register — 二次开发说明

> **原帖**: [linux.do/t/topic/1935408](https://linux.do/t/topic/1935408?u=hjianing424)  
> **本项目仓库**: [github.com/a2447813206/codex-register](https://github.com/a2447813206/codex-register)  
> **邮箱 API 购买地址**: https://royp.online/

---

## 一、原版项目概述

### 1.1 核心定位

ChatGPT / OpenAI Codex **批量自动注册工具**。纯 HTTP 协议实现注册全流程（无需浏览器），可选 Playwright 支持 Turnstile 验证码挑战。

### 1.2 原版技术栈

| 层级 | 技术选型 |
|------|---------|
| 后端 | Python 3.7+ / Flask / `curl_cffi`（TLS 指纹伪装） |
| 前端 | Vue 3 + Vite + TypeScript + Tailwind CSS |
| UI 组件库 | shadcn/ui（基于 Radix Vue） |
| 图表库 | @unovis/vue |
| 浏览器自动化 | Playwright（Chromium，仅用于 Turnstile） |
| 代理管理 | sing-box（支持 Clash/Mihomo 订阅格式） |
| 实时日志推送 | SSE（Server-Sent Events） |

### 1.3 原版功能清单

| 模块 | 功能描述 |
|------|---------|
| 批量自动注册 | 纯协议完成：创建临时邮箱 → 注册 → OTP 验证 → 账号创建 |
| Codex OAuth | PKCE 流程自动交换 Access Token / Refresh Token |
| Sentinel Token 双引擎 | 纯 Python PoW（快）+ Playwright Turnstile（稳），智能切换 |
| 多邮箱提供商 | DuckMail / Cloudflare Mail Worker / YYDS Mail（**原版仅此 3 种**） |
| 代理支持 | 固定代理（`user:pass@host:port`）/ SingBox 动态轮换 |
| Web 管理面板 | Vue 3 可视化控制台：仪表盘 / 注册任务 / 账号库 / 设置页 |

### 1.4 原版注册流程（9 步）

```
┌─────────────────────────────────────────────────────────────┐
│                     V3 注册全流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1   访问 chatgpt.com 首页 → 建立 session               │
│    ↓                                                           │
│  Step 2   获取 CSRF token                                     │
│    ↓                                                           │
│  Step 3   POST signin (login_hint=email)                      │
│    ↓                                                           │
│  Step 4   GET authorize → 重定向到密码页                       │
│    ↓                                                           │
│  Step 5   POST register (Sentinel+Turnstile) → 设置密码       │
│    ↓                                                           │
│  Step 6   发送 OTP → 轮询邮箱验证码 → validate_otp            │
│    ↓                                                           │
│  Step 7   POST create_account (Sentinel+Turnstile)            │
│    ↓                                                           │
│  Step 8   [可选] 绕过 add-phone（3 种策略）                    │
│    ↓                                                           │
│  Step 9   Callback → PKCE OAuth Token 交换                    │
│    ↓                                                           │
│  ✅ 保存: codex_tokens/{email}.json + ak.txt + rk.txt         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、二次开发改动详解

### 改动概览

| 序号 | 改动模块 | 改动类型 | 影响范围 | 优先级 |
|:----:|---------|:-------:|:--------:|:-----:|
| 1 | **新增 MailAPI.ICU 邮箱提供商（含批量池）** | 新功能 | `config_loader.py` + `config.json` + 前端 | P0 核心 |
| 2 | **广告横幅系统（前后端双保险）** | 新功能 | `AppLayout.vue` + `api.py` | P1 |
| 3 | **OAuth 模型映射扩展至 GPT-5.x 系列** | 增强 | `config_loader.py` | P2 |
| 4 | **Token 自动上传到管理平台** | 增强 | `config_loader.py` + `config.json` | P2 |

---

### 2.1 🆕 核心二开：MailAPI.ICU 邮箱提供商（批量池）

#### 2.1.1 改动背景

原版支持的 3 种邮箱都是 **API 动态创建一次性临时邮箱**，用完即弃。但实际生产中用户往往有**大量已有的 Hotmail/Outlook 邮箱**，希望通过**统一的取件 API** 接收验证码邮件，并支持**多邮箱轮换**以分散风险。

#### 2.1.2 改动位置

| 文件 | 行号 | 改动内容 |
|------|:----:|---------|
| `config_loader.py` | 87~169 | 新增 MailAPI.ICU 配置加载与全局变量 |
| `config_loader.py` | 1556~1610 | `ChatGPTRegister` 类新增 3 个方法 |
| `config_loader.py` | 1627~1645 | 邮箱分发器 `_fetch_emails()` / `_fetch_email_detail()` 适配 |
| `config_loader.py` | 192~194, 2789~2792 | 启动检查与 `run_batch()` 校验 |
| `config.json` | — | 新增 `mailapi_icu_*` 配置段 |
| `frontend/src/views/settings/` | — | 邮箱设置页面增加 MailAPI.ICU 表单和批量导入 |

#### 2.1.3 配置层改动（`config_loader.py` 第 87~169 行）

```python
# ========== 新增：MailAPI.ICU 全局变量 ==========
MAILAPI_ICU_EMAIL = _CONFIG.get("mailapi_icu_email", "").strip()
MAILAPI_ICU_ORDER_NO = _CONFIG.get("mailapi_icu_order_no", "").strip()
MAILAPI_ICU_API_BASE = "https://mailapi.icu"

# 批量导入池：从 API URL 中自动提取 orderNo
MAILAPI_ICU_BULK: list = []           # ← 批量邮箱列表
MAILAPI_ICU_BULK_INDEX = 0            # ← 轮换索引（Round-Robin）
MAILAPI_ICU_BULK_LOCK = threading.Lock()  # ← 线程安全锁
```

**批量池解析逻辑**：

```python
# 从 config.json 的 mailapi_icu_bulk 数组解析
_raw_bulk = _CONFIG.get("mailapi_icu_bulk", [])
if isinstance(_raw_bulk, list):
    for item in _raw_bulk:
        if not isinstance(item, dict):
            continue
        email = (item.get("email") or "").strip()
        api_url = (item.get("api_url") or "").strip()
        if email and api_url:
            # 从 URL 中自动提取 orderNo 参数
            order_no = ""
            try:
                parsed = urlparse(api_url)
                qs = parse_qs(parsed.query)
                order_no = qs.get("orderNo", [""])[0]
            except Exception:
                pass
            MAILAPI_ICU_BULK.append({
                "email": email,
                "order_no": order_no,
                "api_url": api_url
            })
```

#### 2.1.4 核心方法实现（`config_loader.py` 第 1558~1581 行）

```python
def _create_temp_email_mailapi_icu(self):
    """MailAPI.ICU: 使用已有邮箱 + 订单号，支持批量轮换"""
    
    # ★★★ 优先使用批量池（核心二开逻辑）
    if MAILAPI_ICU_BULK:
        global MAILAPI_ICU_BULK_INDEX
        with MAILAPI_ICU_BULK_LOCK:          # 加锁保证线程安全
            idx = MAILAPI_ICU_BULK_INDEX % len(MAILAPI_ICU_BULK)  # 取模轮换
            item = MAILAPI_ICU_BULK[idx]
            MAILAPI_ICU_BULK_INDEX += 1     # 索引前进
        email = item["email"]
        order_no = item["order_no"]
        password = _generate_password()      # 生成 ChatGPT 密码（非邮箱密码）
        print(f"  [MailAPI.ICU] 批量池 #{idx+1}/{len(MAILAPI_ICU_BULK)}: {email}")
        return email, password, order_no
    
    # Fallback：单个邮箱模式（兼容旧配置）
    if not MAILAPI_ICU_EMAIL:
        raise Exception("mailapi_icu_email 未设置，且批量池为空")
    if not MAILAPI_ICU_ORDER_NO:
        raise Exception("mailapi_icu_order_no 未设置，且批量池为空")
    password = _generate_password()
    mail_token = MAILAPI_ICU_ORDER_NO
    print(f"  [MailAPI.ICU] 使用固定邮箱: {MAILAPI_ICU_EMAIL}")
    return MAILAPI_ICU_EMAIL, password, mail_token
```

**邮件取件实现**（第 1583~1605 行）：

```python
def _fetch_emails_mailapi_icu(self, mail_token: str):
    """MailAPI.ICU: 通过 orderNo 获取邮件列表"""
    session = self._create_duckmail_session()
    res = session.get(
        f"{MAILAPI_ICU_API_BASE}/key",
        params={"orderNo": mail_token, "type": "json"},  # JSON 格式取件
        timeout=120,  # 长超时等待验证码邮件
    )
    if res.status_code == 200:
        data = res.json()
        if isinstance(data, list) and len(data) > 0 and data[0].get("error"):
            return []
        return data if isinstance(data, list) else []
    return []
```

#### 2.1.5 分发器适配（第 1627~1645 行）

在原有 DuckMail / CF / YYDS 的 if-else 分支中新增 MailAPI.ICU 分支：

```python
def _fetch_emails(self, mail_token: str):
    """根据 MAIL_PROVIDER 调用对应的 fetch"""
    if MAIL_PROVIDER == "cloudflare":
        return self._fetch_emails_cf(mail_token)
    if MAIL_PROVIDER == "yyds_mail":
        return self._fetch_emails_yyds(mail_token)
    if MAIL_PROVIDER == "mailapi_icu":          # ← 新增分支
        return self._fetch_emails_mailapi_icu(mail_token)
    return self._fetch_emails_duckmail(mail_token)  # 默认 DuckMail


def _fetch_email_detail(self, mail_token: str, msg_id: str):
    """根据 MAIL_PROVIDER 调用对应的 detail"""
    if MAIL_PROVIDER == "cloudflare":
        return self._fetch_email_detail_cf(mail_token, msg_id)
    if MAIL_PROVIDER == "yyds_mail":
        return self._fetch_email_detail_yyds(mail_token, msg_id)
    if MAIL_PROVIDER == "mailapi_icu":          # ← 新增分支
        return self._fetch_email_detail_mailapi_icu(mail_token, msg_id)
    return self._fetch_email_detail_duckmail(mail_token, msg_id)
```

#### 2.1.6 配置格式

**方式 A — 批量池模式（推荐，核心功能）**：

```jsonc
{
  "mail_provider": "mailapi_icu",
  "mailapi_icu_bulk": [
    {
      "email": "user1@hotmail.com",
      "api_url": "https://mailapi.icu/key?type=html&orderNo=订单号1"
    },
    {
      "email": "user2@hotmail.com",
      "api_url": "https://mailapi.icu/key?type=html&orderNo=订单号2"
    },
    {
      "email": "user3@hotmail.com",
      "api_url": "https://mailapi.icu/key?type=html&orderNo=订单号3"
    }
  ]
}
```

**方式 B — 单个邮箱（兼容旧配置）**：

```jsonc
{
  "mail_provider": "mailapi_icu",
  "mailapi_icu_email": "your@hotmail.com",
  "mailapi_icu_order_no": "你的订单号"
}
```

**Web 面板批量导入格式**（在「邮箱设置」页面文本框粘贴）：

```
邮箱地址----取件API地址
user1@hotmail.com----https://mailapi.icu?key?type=html&orderNo=xxxxx
user2@hotmail.com----https://mailapi.icu?key?type=html&orderNo=yyyyy
user3@hotmail.com----https://mailapi.icu?key?type=html&orderNo=zzzzz
```

#### 2.1.7 原版 vs 二开 对比

| 维度 | 原版 3 种邮箱 | 二开 MailAPI.ICU |
|:-----|:------------|:----------------|
| **邮箱来源** | API 实时创建（一次性临时） | **已有邮箱池（可长期复用）** |
| **批量机制** | 无（每次新建一个） | **预导入 N 个，Round-Robin 轮换** |
| **并发安全** | 天然安全（每次独立） | **`MAILAPI_ICU_BULK_LOCK` 线程锁** |
| **取件协议** | 各私有 API（DuckMail/CF/YYDS 各不同） | **统一 `mailapi.icu/key` REST API** |
| **失败处理** | 失败即丢弃 | **失败不消耗同邮箱次数，下一个继续** |
| **Web 导入** | 不支持 | **支持文本框批量粘贴导入** |
| **适用场景** | 少量测试 | **大规模量产（100+ 账号）** |

---

### 2.2 广告横幅系统

#### 2.2.1 改动背景

开源项目需要商业化推广渠道，在 Web 面板顶部植入广告横幅，推广邮箱 API 购买服务。

#### 2.2.2 改动位置

| 文件 | 改动 |
|------|------|
| `frontend/src/layouts/AppLayout.vue` | 新增顶部静态横幅组件 |
| `src/routes/api.py` | 新增 `GET /api/banner` 接口（后端下发预留） |

#### 2.2.3 前端实现 (`AppLayout.vue`)

**布局关键点：横幅必须放在 `<SidebarProvider>` 外面**

```vue
<template>
  <!-- ✅ 顶部横幅：放在 SidebarProvider 外层，不破坏 CSS Grid 布局 -->
  <div
    v-if="BANNER.text"
    class="w-full text-center text-white text-sm py-2 px-4 z-[60] relative"
    :style="{ background: BANNER_GRADIENT }"
  >
    <span>{{ BANNER.text }}</span>
    <a
      v-if="BANNER.button_url"
      :href="BANNER.button_url"
      target="_blank"
      rel="noopener noreferrer"
      class="ml-3 inline-flex items-center rounded-full bg-white/20 hover:bg-white/30 
             backdrop-blur-sm px-4 py-1 font-medium transition-colors cursor-pointer"
    >
      {{ BANNER.button_text }}
    </a>
  </div>

  <!-- ⚠️ SidebarProvider 内部不可放其他同级元素，否则破坏 Grid -->
  <SidebarProvider>
    <Sidebar variant="sidebar" collapsible="icon">
      <!-- 侧边栏导航 ... -->
    </Sidebar>
    <SidebarInset>
      <header>...</header>
      <main><router-view /></main>
    </SidebarInset>
  </SidebarProvider>
</template>
```

**脚本部分（静态对象，非异步加载）**：

```js
// 横幅配置（硬编码静态对象）
const BANNER = {
  text: '该源码仅支持邮箱----取件api  购买邮箱地址',
  button_text: '前往购买',
  button_url: 'https://royp.online/',
}
const BANNER_GRADIENT = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
```

> **为什么用静态而非异步 API？**  
> 经验教训：之前尝试通过 `onMounted` 异步调用 `/api/banner` 获取配置，导致 Vue 组件渲染时序异常、白屏崩溃。最终改用**静态硬编码**方案，简单可靠。

#### 2.2.4 后端接口 (`src/routes/api.py`)

```python
# 横幅广告配置（后端下发备用，为将来动态化预留）
_BANNER_CONFIG = {
    "text": "该源码仅支持邮箱----取件api  购买邮箱地址",
    "button_text": "前往购买",
    "button_url": "https://royp.online/",
}

@api_bp.route("/banner", methods=["GET"])
def get_banner():
    """返回横幅广告配置，前端可选择性调用"""
    return jsonify(_BANNER_CONFIG)
```

#### 2.2.5 设计决策记录

| 决策点 | 方案选择 | 原因 |
|:-------|:-------|:-----|
| 数据来源 | 静态硬编码 | 避免 async onMounted 导致 Vue 白屏 |
| 布局位置 | SidebarProvider 外层 | 防止破坏 CSS Grid 主布局 |
| z-index | 60 | 高于侧边栏(z-30)和 header，确保最顶层显示 |
| 后端接口 | 保留 `/api/banner` | 为将来动态下发 / A/B 测试预留能力 |
| 渐变配色 | `#667eea → #764ba2` | 科技感紫蓝渐变，视觉舒适 |

---

### 2.3 OAuth 模型映射扩展

#### 改动位置
`config_loader.py` 第 517~573 行 — `_build_default_model_mapping()` 函数

#### 改动内容
将 OpenAI 模型映射表从原版的 GPT-4o/o1/o3 系列扩展至 **GPT-5.x 全系列**：

```python
def _build_default_model_mapping() -> dict:
    return {
        # ===== 原版模型（保留）=====
        "gpt-3.5-turbo": "gpt-3.5-turbo",
        "gpt-4": "gpt-4",
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "o1": "o1",
        "o1-mini": "o1-mini",
        "o3": "o3",
        "o3-mini": "o3-mini",
        
        # ===== 二开新增：GPT-5.x 系列 =====
        "gpt-5": "gpt-5",
        "gpt-5-2025-08-07": "gpt-5-2025-08-07",
        "gpt-5-chat": "gpt-5-chat",
        "gpt-5-codex": "gpt-5-codex",              # Codex 专用
        "gpt-5-pro": "gpt-5-pro",
        "gpt-5-mini": "gpt-5-mini",
        "gpt-5-nano": "gpt-5-nano",
        "gpt-5.1": "gpt-5.1",
        "gpt-5.1-codex": "gpt-5.1-codex",          # Codex 专用
        "gpt-5.1-codex-max": "gpt-5.1-codex-max",
        "gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
        "gpt-5.2": "gpt-5.2",
        "gpt-5.2-codex": "gpt-5.2-codex",          # Codex 专用
        "gpt-5.2-pro": "gpt-5.2-pro",
        "gpt-5.3-codex": "gpt-5.3-codex",          # Codex 专用
        "gpt-5.3-codex-spark": "gpt-5.3-codex-spark",
        "gpt-5.4": "gpt-5.4",
        "chatgpt-4o-latest": "chatgpt-4o-latest",
        # ... 更多模型
    }
```

---

### 2.4 Token 自动上传到管理平台

#### 改动位置
- `config_loader.py`: 第 677~706 行（上传逻辑）、183~184 行（配置读取）
- `config.json`: 新增 `upload_api_url` 和 `upload_api_token` 字段

#### 功能说明

注册成功并获取 OAuth Token 后，自动将 Token JSON 文件上传到远程管理平台：

```python
def _upload_token_json(filepath):
    """上传 Token 到管理平台"""
    import requests as std_requests
    session = std_requests.Session()
    session.verify = False
    if DEFAULT_PROXY:
        session.proxies = {"http": DEFAULT_PROXY, "https": DEFAULT_PROXY}
    with open(filepath, "rb") as f:
        resp = session.post(
            UPLOAD_API_URL,
            files={"file": (filename, f, "application/json")},
            headers={"Authorization": f"Bearer {UPLOAD_API_TOKEN}"},
            timeout=30,
        )
```

**配置项**：
```jsonc
{
  "upload_api_url": "https://your-api.example.com/upload",
  "upload_api_token": "your-bearer-token"
}
```

---

## 三、完整文件变更清单

### 3.1 修改文件汇总

| 文件 | 改动行数（估算） | 改动类型 |
|:-----|:---------------:|:--------|
| `config_loader.py` | ~250 行 | 新增 MailAPI.ICU 全套逻辑 + 模型扩展 + 上传功能 |
| `src/routes/api.py` | ~12 行 | 新增 `/api/banner` 接口 |
| `frontend/src/layouts/AppLayout.vue` | ~75 行 | 新增横幅模板 + 脚本 |
| `config.json` | ~20 行 | 新增配置字段 |
| 前端邮箱设置页面 | ~50 行 | 新增 MailAPI.ICU 表单控件 |

### 3.2 未修改的核心文件（保持原版不变）

以下文件**完全保留原版代码**，未做任何修改：

| 文件 | 说明 |
|------|------|
| `app.py` | Flask 入口 |
| `playwright_sentinel.py` | Playwright Sentinel + Turnstile 引擎 |
| `sentinel_sdk_version.py` | SDK 版本动态探测 |
| `src/__init__.py` | Flask 工厂函数 |
| `src/routes/pages.py` | 页面路由 |
| `src/services/task.py` | 任务调度（进程池） |
| `src/services/singbox.py` | SingBox 代理管理 |
| `src/services/singbox_cache.py` | 节点健康缓存 |
| `src/services/logger.py` | SSE 日志广播 |
| `src/services/clash_subscription.py` | Clash 订阅解析 |
| `requirements.txt` | Python 依赖 |
| `start.sh` | 启动脚本 |

---

## 四、二开架构图

```
==================== 二开前（原版）====================
                          ||
                          \\/
==================== 二开后（当前版本）==================

【后端 - config_loader.py】

  mail_provider 分发器
  ├── duckmail      → _create_temp_email_duckmail()      ← 原版
  ├── cloudflare    → _create_temp_email_cf()             ← 原版
  ├── yyds_mail     → _create_temp_email_yyds()           ← 原版
  └── mailapi_icu ★ → _create_temp_email_mailapi_icu() ★ ← ★★★ 二开
                       ├── 单个邮箱模式（兼容）
                       └── 批量池模式 ★★★★★
                           ├── MAILAPI_ICU_BULK[]     ← 配置数组
                           ├── MAILAPI_ICU_BULK_INDEX ← Round-Robin 索引
                           └── MAILAPI_ICU_BULK_LOCK ← threading.Lock
  
  邮箱取件分发器 (_fetch_emails)
  ├── duckmail      → _fetch_emails_duckmail()           ← 原版
  ├── cloudflare    → _fetch_emails_cf()                 ← 原版
  ├── yyds_mail     → _fetch_emails_yyds()               ← 原版
  └── mailapi_icu ★ → _fetch_emails_mailapi_icu() ★      ← ★★ 二开
                       (mailapi.icu/key?type=json&orderNo=xxx)

  OAuth 模型映射
  ├── 原版: gpt-3.5/4/4o/o1/o3 系列                     ← 原版
  └── 新增: gpt-5/5.1/5.2/5.3/5.4/codex 系列            ← ★★ 二开

  Token 输出
  ├── 本地保存: codex_tokens/{email}.json + ak.txt + rk.txt  ← 原版
  └── 远程上传: POST upload_api_url (Bearer token)             ← ★★ 二开


【后端 - src/routes/api.py】

  GET  /api/banner → {text, button_text, button_url}          ← ★★ 二开
  GET  /config                                                 ← 原版
  POST /config                                                 ← 原版
  POST /start                                                  ← 原版
  ...其余接口全部保持原版...


【前端 - AppLayout.vue】

  原版布局: SidebarProvider (纯工具面板)
                    ||
                    \\/
  二开后布局:
  ┌──────────────────────────────────────┐
  │ 📢 广告横幅 (z-index: 60) ★           │ ← SidebarProvider 外层
  │ 该源码仅支持邮箱... [前往购买]         │
  ├──────────────────────────────────────┤
  │  SidebarProvider (原版布局不变)        │
  │  ├── Sidebar (侧边栏导航)             │
  │  └── SidebarInset                    │
  │      ├── Header (面包屑 + 主题切换)   │
  │      ├── Main (<router-view />)      │
  │      └── LogCenter (SSE 日志)        │
  └──────────────────────────────────────┘
```

---

## 五、如何基于本二开版本继续开发

### 5.1 新增邮箱提供商（参考 MailAPI.ICU 模式）

如果需要支持第 5 种邮箱服务商，按以下步骤操作：

**Step 1 — `config_loader.py` 配置层**

```python
# 在 _load_config() 中新增字段解析（约第 88~102 行）
config["your_provider_email"] = os.environ.get("YOUR_EMAIL", config.get("your_provider_email", ""))
config["your_provider_api_key"] = os.environ.get("YOUR_API_KEY", config.get("your_provider_api_key", ""))

# 新增全局变量（约第 144~169 行区域）
YOUR_PROVIDER_EMAIL = _CONFIG.get("your_provider_email", "").strip()
YOUR_PROVIDER_API_KEY = _CONFIG.get("your_provider_api_key", "").strip()
```

**Step 2 — `ChatGPTRegister` 类新增方法**

```python
def _create_temp_email_your_provider(self):
    """你的邮箱提供商：创建/选取邮箱"""
    # 调用你的 API...
    email = "xxx@domain.com"
    password = _generate_password()
    token = "api_token_or_id"
    return email, password, token

def _fetch_emails_your_provider(self, mail_token):
    """取件"""
    session = self._create_duckmail_session()
    res = session.get(f"https://your-api.com/fetch?token={mail_token}")
    return res.json()

def _fetch_email_detail_your_provider(self, mail_token, msg_id):
    """详情"""
    return None  # 如果列表已包含完整信息
```

**Step 3 — 分发器添加分支**

```python
# _fetch_emails() 中新增：
if MAIL_PROVIDER == "your_provider":
    return self._fetch_emails_your_provider(mail_token)

# _fetch_email_detail() 中新增：
if MAIL_PROVIDER == "your_provider":
    return self._fetch_email_detail_your_provider(mail_token, msg_id)
```

**Step 4 — 启动检查与 run_batch 校验**

```python
elif MAIL_PROVIDER == "your_provider":
    if not YOUR_PROVIDER_API_KEY:
        print("警告: 未设置 your_provider_api_key")
```

### 5.2 移除/替换广告横幅

编辑 `frontend/src/layouts/AppLayout.vue`：

```js
// 方案一：完全移除
const BANNER = { text: '', button_text: '', button_url: '' }

// 方案二：替换为你的广告
const BANNER = {
  text: '你的广告文案',
  button_text: '点击查看',
  button_url: 'https://your-link.com/',
}
```

同时修改 `src/routes/api.py` 中的 `_BANNER_CONFIG` 保持一致。

---

## 六、环境变量覆盖列表

所有 `config.json` 配置项均可通过环境变量覆盖（优先级高于配置文件）：

| 环境变量 | 对应 config.json 字段 | 说明 |
|---------|----------------------|------|
| `MAIL_PROVIDER` | `mail_provider` | 邮箱提供商 |
| `MAILAPI_ICU_EMAIL` | `mailapi_icu_email` | ICU 单邮箱 |
| `MAILAPI_ICU_ORDER_NO` | `mailapi_icu_order_no` | ICU 订单号 |
| `PROXY` | `proxy` | 代理地址 |
| `TOTAL_ACCOUNTS` | `total_accounts` | 注册数量 |
| `ENABLE_OAUTH` | `enable_oauth` | OAuth 开关 |
| `UPLOAD_API_URL` | `upload_api_url` | Token 上传地址 |
| `UPLOAD_API_TOKEN` | `upload_api_token` | 上传认证 Token |

---

## 七、注意事项

1. **MailAPI.ICU 批量池的线程安全**: 并发注册时务必使用 `MAILAPI_ICU_BULK_LOCK`，否则可能出现同一邮箱被多个线程同时使用的问题。

2. **横幅布局位置**: **绝对不能**把横幅 `<div>` 放入 `<SidebarProvider>` 内部，会导致 CSS Grid 布局崩溃、页面白屏。这是踩过坑的经验教训。

3. **Sentinel SDK 版本探测**: `sentinel_sdk_version.py` 会自动从 OpenAI 服务器获取最新版本号并缓存 1 小时。如果 OpenAI 更新了 Sentinel SDK，无需手动改代码，程序会自动适配。

4. **Playwright 安装是可选但强烈推荐的**: 没有 Playwright 时回退到纯 HTTP PoW 模式（无 Turnstile t 字段），写操作（register/create_account）可能被 OpenAI 拒绝。

5. **`config.json` 已加入 `.gitignore`**: 包含敏感信息（代理密码、邮箱 API Key 等），不会被提交到 Git 仓库。

---

> **文档版本**: v1.0  
> **最后更新**: 2026-04-10  
> **适用项目**: codex-register (基于 linux.do/t/topic/1935408 二次开发)