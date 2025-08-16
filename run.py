#!/usr/bin/env python3
"""
启动脚本 - 孔夫子旧书网销售数据分析系统
使用方法: uv run python run.py
"""

import asyncio
import logging
import uvicorn
import os

# 开启Python开发模式调试
os.environ["PYTHONDEVMODE"] = "1"

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug.log', encoding='utf-8')
    ]
)

# 设置特定模块的日志级别
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)

# 获取并配置asyncio事件循环调试
def setup_asyncio_debug():
    """设置asyncio调试模式"""
    try:
        loop = asyncio.get_event_loop()
        loop.set_debug(True)
        logging.info("已开启asyncio调试模式")
    except RuntimeError:
        # 如果没有事件循环，创建一个
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        logging.info("创建并开启asyncio调试模式")

if __name__ == "__main__":
    setup_asyncio_debug()
    
    # 添加运行时监控
    logging.info("=" * 60)
    logging.info("启动孔夫子旧书网销售数据分析系统")
    logging.info("调试模式: 已开启")
    logging.info("日志级别: DEBUG")
    logging.info("=" * 60)
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8282,
        reload=True,
        reload_dirs=["src"],
        log_level="debug"
    )