#!/usr/bin/env python3
"""
简化的任务队列 - 业务层只需要关心任务的增删改查
所有窗口管理和任务执行由AutonomousSessionManager自主处理
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..models.repositories import CrawlTaskRepository
from ..models.models import CrawlTask

logger = logging.getLogger(__name__)


class SimpleTaskQueue:
    """简化的任务队列 - 业务层接口"""
    
    def __init__(self):
        self.task_repo = CrawlTaskRepository()
    
    def add_task(self, 
                 task_name: str,
                 task_type: str, 
                 target_platform: str,
                 target_url: str = None,
                 target_isbn: str = None,
                 shop_id: int = None,
                 book_title: str = None,
                 task_params: Dict[str, Any] = None,
                 priority: int = 5) -> int:
        """添加单个任务到队列
        
        Args:
            task_name: 任务名称
            task_type: 任务类型 (book_sales_crawl, shop_books_crawl, duozhuayu_price, isbn_analysis)
            target_platform: 目标平台 (kongfuzi, duozhuayu, taobao)
            target_url: 目标URL（可选）
            target_isbn: 目标ISBN（可选）
            shop_id: 店铺ID（可选）
            book_title: 书籍标题（可选）
            task_params: 额外参数（可选）
            priority: 优先级 1-10，数字越大优先级越高
            
        Returns:
            任务ID
        """
        task = CrawlTask(
            task_name=task_name,
            task_type=task_type,
            target_platform=target_platform,
            target_url=target_url,
            target_isbn=target_isbn,
            shop_id=shop_id,
            book_title=book_title,
            task_params=task_params,
            priority=priority,
            status='pending'
        )
        
        task_id = self.task_repo.create(task)
        logger.info(f"添加任务: {task_id} - {task_name} ({target_platform})")
        return task_id
    
    def add_book_sales_task(self, isbn: str, shop_id: int, book_title: str = None, priority: int = 5) -> int:
        """添加书籍销售记录爬取任务"""
        task_name = f"爬取《{book_title or isbn}》销售记录"
        return self.add_task(
            task_name=task_name,
            task_type='book_sales_crawl',
            target_platform='kongfuzi',
            target_isbn=isbn,
            shop_id=shop_id,
            book_title=book_title,
            priority=priority
        )
    
    def add_shop_books_task(self, shop_url: str, shop_id: int, max_pages: int = 50, priority: int = 5) -> int:
        """添加店铺书籍列表爬取任务"""
        task_name = f"爬取店铺书籍列表"
        return self.add_task(
            task_name=task_name,
            task_type='shop_books_crawl',
            target_platform='kongfuzi',
            target_url=shop_url,
            shop_id=shop_id,
            task_params={'max_pages': max_pages},
            priority=priority
        )
    
    def add_price_update_task(self, isbn: str, shop_id: int, priority: int = 3) -> int:
        """添加价格更新任务"""
        task_name = f"更新《{isbn}》价格信息"
        return self.add_task(
            task_name=task_name,
            task_type='duozhuayu_price',
            target_platform='duozhuayu',
            target_isbn=isbn,
            shop_id=shop_id,
            priority=priority
        )
    
    def add_isbn_analysis_task(self, isbn: str, priority: int = 7) -> int:
        """添加ISBN分析任务"""
        task_name = f"分析《{isbn}》销售数据"
        return self.add_task(
            task_name=task_name,
            task_type='isbn_analysis',
            target_platform='kongfuzi',
            target_isbn=isbn,
            priority=priority
        )
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        pending_count = self.task_repo.get_platform_task_count('kongfuzi', 'pending')
        running_count = self.task_repo.get_platform_task_count('kongfuzi', 'running')
        
        # 按平台统计
        platforms = ['kongfuzi', 'duozhuayu', 'taobao']
        platform_stats = {}
        
        for platform in platforms:
            platform_stats[platform] = {
                'pending': self.task_repo.get_platform_task_count(platform, 'pending'),
                'running': self.task_repo.get_platform_task_count(platform, 'running'),
                'completed_today': self._get_today_completed_count(platform),
                'failed_today': self._get_today_failed_count(platform)
            }
        
        return {
            'total_pending': pending_count,
            'total_running': running_count,
            'platform_stats': platform_stats,
            'recent_tasks': self.get_recent_tasks(limit=10)
        }
    
    def _get_today_completed_count(self, platform: str) -> int:
        """获取今天完成的任务数量"""
        try:
            from ..models.database import db
            query = """
                SELECT COUNT(*) FROM crawl_tasks 
                WHERE target_platform = ? AND status = 'completed' 
                AND DATE(end_time) = DATE('now')
            """
            result = db.execute_query(query, (platform,))
            return result[0]['COUNT(*)'] if result else 0
        except:
            return 0
    
    def _get_today_failed_count(self, platform: str) -> int:
        """获取今天失败的任务数量"""
        try:
            from ..models.database import db
            query = """
                SELECT COUNT(*) FROM crawl_tasks 
                WHERE target_platform = ? AND status = 'failed' 
                AND DATE(created_at) = DATE('now')
            """
            result = db.execute_query(query, (platform,))
            return result[0]['COUNT(*)'] if result else 0
        except:
            return 0
    
    def get_recent_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的任务"""
        return self.task_repo.get_recent_tasks(limit)
    
    def get_pending_tasks(self, platform: str = None) -> List[Dict[str, Any]]:
        """获取待处理任务"""
        if platform:
            return self.task_repo.get_pending_tasks_by_platform(platform)
        else:
            return self.task_repo.get_pending_tasks()
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取任务"""
        return self.task_repo.get_by_id(task_id)
    
    def cancel_task(self, task_id: int) -> bool:
        """取消任务（只能取消pending状态的任务）"""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            return False
        
        if task['status'] != 'pending':
            logger.warning(f"任务 {task_id} 状态为 {task['status']}，无法取消")
            return False
        
        return self.task_repo.update_status(task_id, 'cancelled')
    
    def retry_failed_tasks(self, platform: str = None) -> int:
        """重试失败的任务"""
        try:
            from ..models.database import db
            
            # 构建查询条件
            if platform:
                query = "SELECT id FROM crawl_tasks WHERE status = 'failed' AND target_platform = ?"
                params = (platform,)
            else:
                query = "SELECT id FROM crawl_tasks WHERE status = 'failed'"
                params = ()
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                failed_tasks = cursor.fetchall()
                
                if not failed_tasks:
                    return 0
                
                # 更新状态为pending
                failed_task_ids = [task[0] for task in failed_tasks]
                placeholders = ",".join(["?"] * len(failed_task_ids))
                update_query = f"UPDATE crawl_tasks SET status = 'pending', error_message = NULL WHERE id IN ({placeholders})"
                cursor.execute(update_query, failed_task_ids)
                
                updated_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"重试了 {updated_count} 个失败的任务")
                return updated_count
                
        except Exception as e:
            logger.error(f"重试失败任务时出错: {e}")
            return 0
    
    def clear_pending_tasks(self, platform: str = None) -> int:
        """清空待处理任务"""
        try:
            from ..models.database import db
            
            if platform:
                query = "DELETE FROM crawl_tasks WHERE status = 'pending' AND target_platform = ?"
                params = (platform,)
            else:
                query = "DELETE FROM crawl_tasks WHERE status = 'pending'"
                params = ()
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"清空了 {deleted_count} 个待处理任务")
                return deleted_count
                
        except Exception as e:
            logger.error(f"清空任务时出错: {e}")
            return 0
    
    def batch_add_isbn_tasks(self, isbn_list: List[str], priority: int = 5) -> List[int]:
        """批量添加ISBN相关任务"""
        task_ids = []
        
        for isbn in isbn_list:
            # 添加销售记录爬取任务
            sales_task_id = self.add_book_sales_task(isbn, shop_id=1, priority=priority)
            task_ids.append(sales_task_id)
            
            # 添加价格更新任务
            price_task_id = self.add_price_update_task(isbn, shop_id=1, priority=priority-1)
            task_ids.append(price_task_id)
        
        logger.info(f"批量添加了 {len(task_ids)} 个任务，涉及 {len(isbn_list)} 个ISBN")
        return task_ids
    
    def cleanup_old_tasks(self, days_old: int = 7) -> int:
        """清理旧的已完成任务"""
        return self.task_repo.cleanup_old_completed_tasks(days_old)


# 全局实例
simple_task_queue = SimpleTaskQueue()