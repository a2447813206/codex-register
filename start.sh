#!/bin/bash

# ============================================
# Codex Register 项目启动脚本
# 作者: wangqiupei
# 功能: 自动检测环境、安装依赖、启动 Flask 服务
# ============================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log_info "项目目录: $SCRIPT_DIR"

# ============================================
# 1. 检测 Python 环境
# ============================================
log_info "检测 Python 环境..."

if ! command -v python3 &> /dev/null; then
    log_error "未找到 python3，请先安装 Python 3.7+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
log_success "Python 版本: $PYTHON_VERSION"

# ============================================
# 2. 检测并创建虚拟环境
# ============================================
VENV_DIR="venv"

if [ ! -d "$VENV_DIR" ]; then
    log_info "未找到虚拟环境，正在创建..."
    python3 -m venv "$VENV_DIR"
    log_success "虚拟环境创建成功"
else
    log_info "虚拟环境已存在"
fi

# 激活虚拟环境
log_info "激活虚拟环境..."
source "$VENV_DIR/bin/activate"

# ============================================
# 3. 检测并安装依赖
# ============================================
log_info "检查依赖..."

# 检查关键模块是否可导入
check_module() {
    python3 -c "import $1" 2>/dev/null
    return $?
}

NEED_INSTALL=false

# 检查核心依赖
if ! check_module "flask"; then
    log_warning "缺少依赖: flask"
    NEED_INSTALL=true
fi

if ! check_module "requests"; then
    log_warning "缺少依赖: requests"
    NEED_INSTALL=true
fi

if ! check_module "curl_cffi"; then
    log_warning "缺少依赖: curl_cffi"
    NEED_INSTALL=true
fi

# 安装依赖
if [ "$NEED_INSTALL" = true ]; then
    log_info "正在安装依赖..."

    if [ -f "requirements.txt" ]; then
        log_info "使用 requirements.txt 安装依赖"
        pip install -r requirements.txt
        log_success "依赖安装完成"
    else
        log_error "未找到 requirements.txt 文件"
        exit 1
    fi
else
    log_success "所有依赖已满足"
fi

# ============================================
# 4. 检查配置文件
# ============================================
log_info "检查配置文件..."

if [ ! -f "config.json" ]; then
    log_error "未找到 config.json 配置文件"
    exit 1
fi

log_success "配置文件检查通过"

# ============================================
# 5. 创建必要的目录和文件
# ============================================
log_info "初始化项目文件..."

# 创建必要的空文件（如果不存在）
touch ak.txt rk.txt registered_accounts.txt registered_accounts.csv

# 创建 token 目录
mkdir -p codex_tokens

# 初始化 invite_tracker.json（如果不存在）
if [ ! -f "invite_tracker.json" ]; then
    echo "{}" > invite_tracker.json
fi

log_success "项目文件初始化完成"

# ============================================
# 6. 启动 Flask 应用
# ============================================
log_info "启动 Flask 应用..."
echo ""
log_success "=========================================="
log_success "  Codex Register 服务启动中..."
log_success "  访问地址: http://127.0.0.1:5001"
log_success "=========================================="
echo ""

# 设置 Flask 环境变量
export FLASK_APP=app.py
export FLASK_ENV=development

# 启动应用（支持命令行参数）
if [ $# -eq 0 ]; then
    # 默认启动方式
    python3 app.py
else
    # 传递命令行参数
    python3 app.py "$@"
fi
