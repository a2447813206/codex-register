"""
ChatGPT 批量注册工具 — Web 管理界面
Flask 后端: 配置管理 / 任务控制 / SSE 实时日志 / 账号管理 / OAuth 导出
"""

import multiprocessing
from src import create_app
from src.utils.config import read_config

app = create_app()

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Windows 需要
    
    print("[INFO] ChatGPT 注册管理面板启动: http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
