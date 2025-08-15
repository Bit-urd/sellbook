#!/usr/bin/env python3
"""
启动脚本 - 孔夫子旧书网销售数据分析系统
使用方法: uv run python run.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8282,
        reload=True,
        reload_dirs=["src"]
    )