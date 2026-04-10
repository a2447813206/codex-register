# -*- mode: python ; coding: utf-8 -*-
"""
Codex Register - PyInstaller 打包配置
用法: pyinstaller codex_register.spec
输出: dist/codex_register.exe
"""

import os
import sys

block_cipher = None

# 项目根目录
project_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(project_dir, 'app.py')],
    pathex=[project_dir],
    binaries=[],
    datas=[
        # 前端构建产物
        ('dist', 'dist'),
        # sing-box 二进制（如果存在）
        ('core', 'core'),
        # 配置模板
        ('README.md', '.'),
    ],
    hiddenimports=[
        'flask',
        'curl_cffi',
        'requests',
        'yaml',
        'socks',
        'playwright',
        'json',
        'multiprocessing',
        'queue',
        'threading',
        'subprocess',
        'uuid',
        're',
        'time',
        'hashlib',
        'base64',
        'secrets',
        'email.utils',
        'html.parser',
        'urllib.parse',
        'pathlib',
        'datetime',
        'random',
        'string',
        'io',
        'zipfile',
        'tempfile',
        'shutil',
        'concurrent.futures',
        'ssl',
        'http.cookiejar',
        'email.mime.multipart',
        'email.mime.text',
        'email.mime.base',
        'email.header',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        os.path.join(project_dir, '_runtime_hook.py'),
    ],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='codex_register',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # 保留控制台窗口（看日志）
    icon=None,
    version=None,
)
