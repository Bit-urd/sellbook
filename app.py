#!/usr/bin/env python3
"""
应用启动脚本
"""
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.main import run_server

if __name__ == "__main__":
    print("=" * 60)
    print("卖书网站价差数据分析系统 v2.0")
    print("=" * 60)
    print("\n系统启动中...")
    print("\n访问地址:")
    print("  主页（数据展示+ISBN搜索）: http://127.0.0.1:8000/")
    print("  销售数据概览: http://127.0.0.1:8000/sales-admin")
    print("  店铺管理: http://127.0.0.1:8000/shop-admin")
    print("  书籍管理: http://127.0.0.1:8000/book-admin")
    print("  爬虫控制页面: http://127.0.0.1:8000/crawler-admin")
    print("  API文档: http://127.0.0.1:8000/docs")
    print("\n按 Ctrl+C 停止服务器")
    print("-" * 60)
    
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        sys.exit(0)