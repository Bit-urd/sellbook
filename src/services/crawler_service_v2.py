#!/usr/bin/env python3
"""
爬虫服务 V2 - 基于自主会话管理器的简化架构
业务层只需要操作任务队列，所有窗口管理和执行由会话管理器自主处理
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any

from .autonomous_session_manager import autonomous_session_manager
from .simple_task_queue import simple_task_queue

logger = logging.getLogger(__name__)


class CrawlerServiceV2:
    """爬虫服务 V2 - 简化的业务接口"""
    
    def __init__(self):
        self.session_manager = autonomous_session_manager
        self.task_queue = simple_task_queue
        # 会话管理器会自动启动，业务层无需关心初始化
    
    async def stop(self):
        """停止爬虫服务"""
        await self.session_manager.stop()
        logger.info("爬虫服务 V2 已停止")
    
    # === 任务管理接口 ===
    
    def add_book_sales_task(self, isbn: str, shop_id: int = 1, book_title: str = None, priority: int = 5) -> int:
        """添加书籍销售记录爬取任务"""
        return self.task_queue.add_book_sales_task(isbn, shop_id, book_title, priority)
    
    def add_shop_books_task(self, shop_url: str, shop_id: int = 1, max_pages: int = 50, priority: int = 5) -> int:
        """添加店铺书籍列表爬取任务"""
        return self.task_queue.add_shop_books_task(shop_url, shop_id, max_pages, priority)
    
    def add_price_update_task(self, isbn: str, shop_id: int = 1, priority: int = 3) -> int:
        """添加价格更新任务"""
        return self.task_queue.add_price_update_task(isbn, shop_id, priority)
    
    def add_isbn_analysis_task(self, isbn: str, priority: int = 7) -> int:
        """添加ISBN分析任务"""
        return self.task_queue.add_isbn_analysis_task(isbn, priority)
    
    def batch_add_isbn_tasks(self, isbn_list: List[str], priority: int = 5) -> List[int]:
        """批量添加ISBN相关任务"""
        return self.task_queue.batch_add_isbn_tasks(isbn_list, priority)
    
    # === 队列管理接口 ===
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        # 合并任务队列状态和会话管理器状态
        task_status = self.task_queue.get_queue_status()
        session_status = await self.session_manager.get_status()
        
        return {
            "task_queue": task_status,
            "session_manager": session_status
        }
    
    def get_recent_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的任务"""
        return self.task_queue.get_recent_tasks(limit)
    
    def get_pending_tasks(self, platform: str = None) -> List[Dict[str, Any]]:
        """获取待处理任务"""
        return self.task_queue.get_pending_tasks(platform)
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取任务"""
        return self.task_queue.get_task_by_id(task_id)
    
    def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        return self.task_queue.cancel_task(task_id)
    
    def retry_failed_tasks(self, platform: str = None) -> int:
        """重试失败的任务"""
        return self.task_queue.retry_failed_tasks(platform)
    
    def clear_pending_tasks(self, platform: str = None) -> int:
        """清空待处理任务"""
        return self.task_queue.clear_pending_tasks(platform)
    
    def cleanup_old_tasks(self, days_old: int = 7) -> int:
        """清理旧的已完成任务"""
        return self.task_queue.cleanup_old_tasks(days_old)
    
    # === 状态监控接口 ===
    
    async def get_window_status(self) -> Dict[str, Any]:
        """获取窗口状态"""
        status = await self.session_manager.get_status()
        return {
            "total_windows": status["total_windows"],
            "available_windows": status["available_windows"],
            "busy_windows": status["busy_windows"],
            "available_by_platform": status["available_by_platform"],
            "sessions": status["sessions"]
        }
    
    async def get_platform_status(self, platform: str) -> Dict[str, Any]:
        """获取特定平台状态"""
        session_status = await self.session_manager.get_status()
        task_status = self.task_queue.get_queue_status()
        
        return {
            "platform": platform,
            "available_windows": session_status["available_by_platform"].get(platform, 0),
            "pending_tasks": task_status["platform_stats"].get(platform, {}).get("pending", 0),
            "running_tasks": task_status["platform_stats"].get(platform, {}).get("running", 0),
            "completed_today": task_status["platform_stats"].get(platform, {}).get("completed_today", 0),
            "failed_today": task_status["platform_stats"].get(platform, {}).get("failed_today", 0)
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        session_status = await self.session_manager.get_status()
        return session_status["statistics"]
    
    # === 便捷方法 ===
    
    def quick_crawl_isbn(self, isbn: str, include_analysis: bool = True) -> List[int]:
        """快速爬取ISBN相关数据"""
        task_ids = []
        
        # 添加销售记录爬取
        sales_task = self.add_book_sales_task(isbn, priority=8)
        task_ids.append(sales_task)
        
        # 添加价格更新
        price_task = self.add_price_update_task(isbn, priority=6)
        task_ids.append(price_task)
        
        # 可选添加分析任务
        if include_analysis:
            analysis_task = self.add_isbn_analysis_task(isbn, priority=9)
            task_ids.append(analysis_task)
        
        logger.info(f"为ISBN {isbn} 添加了 {len(task_ids)} 个任务")
        return task_ids
    
    def emergency_stop_platform(self, platform: str) -> Dict[str, int]:
        """紧急停止特定平台的所有任务"""
        # 清空该平台的待处理任务
        cleared = self.clear_pending_tasks(platform)
        
        # 这里可以进一步实现停止正在运行的任务的逻辑
        # 但由于会话管理器是自主的，我们只能清空队列
        
        logger.warning(f"紧急停止平台 {platform}，清空了 {cleared} 个待处理任务")
        return {
            "platform": platform,
            "cleared_tasks": cleared
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        session_status = await self.session_manager.get_status()
        
        # 检查各种健康指标
        health = {
            "session_manager_running": session_status["running"],
            "browser_connected": session_status["connected"],
            "total_windows": session_status["total_windows"],
            "available_windows": session_status["available_windows"],
            "healthy": True,
            "issues": []
        }
        
        # 检查问题
        if not session_status["running"]:
            health["healthy"] = False
            health["issues"].append("会话管理器未运行")
        
        if not session_status["connected"]:
            health["healthy"] = False
            health["issues"].append("浏览器未连接")
        
        if session_status["available_windows"] == 0:
            health["healthy"] = False
            health["issues"].append("没有可用窗口")
        
        return health


# 全局实例
crawler_service_v2 = CrawlerServiceV2()