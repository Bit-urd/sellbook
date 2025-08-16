#!/usr/bin/env python3
"""
SimpleTaskQueue单元测试
测试纯业务任务队列的增删改查功能
"""
import pytest
import uuid
from unittest.mock import Mock, patch
from datetime import datetime

from src.services.simple_task_queue import SimpleTaskQueue


class TestSimpleTaskQueue:
    """SimpleTaskQueue单元测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.task_queue = SimpleTaskQueue()
        self.unique_id = str(uuid.uuid4())[:8]
    
    def test_add_task_basic(self):
        """测试基本任务添加功能"""
        # 准备测试数据
        task_name = f"测试任务_{self.unique_id}"
        task_type = "book_sales_crawl"
        target_platform = "kongfuzi"
        
        # Mock CrawlTaskRepository.create方法
        with patch.object(self.task_queue.task_repo, 'create') as mock_create:
            mock_create.return_value = 123
            
            # 执行测试
            task_id = self.task_queue.add_task(
                task_name=task_name,
                task_type=task_type,
                target_platform=target_platform,
                target_isbn="9787544291200",
                priority=5
            )
            
            # 验证结果
            assert task_id == 123
            mock_create.assert_called_once()
            
            # 验证传入参数
            call_args = mock_create.call_args[0][0]
            assert call_args.task_name == task_name
            assert call_args.task_type == task_type
            assert call_args.target_platform == target_platform
            assert call_args.target_isbn == "9787544291200"
            assert call_args.priority == 5
            assert call_args.status == 'pending'
    
    def test_add_task_with_optional_params(self):
        """测试带可选参数的任务添加"""
        with patch.object(self.task_queue.task_repo, 'create') as mock_create:
            mock_create.return_value = 124
            
            task_id = self.task_queue.add_task(
                task_name="完整参数任务",
                task_type="shop_books_crawl",
                target_platform="kongfuzi",
                target_url="https://shop123.kongfz.com/",
                shop_id=1,
                book_title="测试书籍",
                task_params={"max_pages": 10},
                priority=8
            )
            
            assert task_id == 124
            call_args = mock_create.call_args[0][0]
            assert call_args.target_url == "https://shop123.kongfz.com/"
            assert call_args.shop_id == 1
            assert call_args.book_title == "测试书籍"
            assert call_args.task_params == {"max_pages": 10}
            assert call_args.priority == 8
    
    def test_add_book_sales_task(self):
        """测试添加书籍销售记录爬取任务"""
        with patch.object(self.task_queue, 'add_task') as mock_add_task:
            mock_add_task.return_value = 125
            
            task_id = self.task_queue.add_book_sales_task(
                isbn="9787544291200",
                shop_id=1,
                book_title="测试书籍",
                priority=7
            )
            
            assert task_id == 125
            mock_add_task.assert_called_once_with(
                task_name="爬取《测试书籍》销售记录",
                task_type='book_sales_crawl',
                target_platform='kongfuzi',
                target_isbn="9787544291200",
                shop_id=1,
                book_title="测试书籍",
                priority=7
            )
    
    def test_add_shop_books_task(self):
        """测试添加店铺书籍列表爬取任务"""
        with patch.object(self.task_queue, 'add_task') as mock_add_task:
            mock_add_task.return_value = 126
            
            task_id = self.task_queue.add_shop_books_task(
                shop_url="https://shop123.kongfz.com/",
                shop_id=1,
                max_pages=20,
                priority=6
            )
            
            assert task_id == 126
            mock_add_task.assert_called_once_with(
                task_name="爬取店铺书籍列表",
                task_type='shop_books_crawl',
                target_platform='kongfuzi',
                target_url="https://shop123.kongfz.com/",
                shop_id=1,
                task_params={'max_pages': 20},
                priority=6
            )
    
    def test_add_price_update_task(self):
        """测试添加价格更新任务"""
        with patch.object(self.task_queue, 'add_task') as mock_add_task:
            mock_add_task.return_value = 127
            
            task_id = self.task_queue.add_price_update_task(
                isbn="9787544291200",
                shop_id=1,
                priority=4
            )
            
            assert task_id == 127
            mock_add_task.assert_called_once_with(
                task_name="更新《9787544291200》价格信息",
                task_type='duozhuayu_price',
                target_platform='duozhuayu',
                target_isbn="9787544291200",
                shop_id=1,
                priority=4
            )
    
    def test_add_isbn_analysis_task(self):
        """测试添加ISBN分析任务"""
        with patch.object(self.task_queue, 'add_task') as mock_add_task:
            mock_add_task.return_value = 128
            
            task_id = self.task_queue.add_isbn_analysis_task(
                isbn="9787544291200",
                priority=9
            )
            
            assert task_id == 128
            mock_add_task.assert_called_once_with(
                task_name="分析《9787544291200》销售数据",
                task_type='isbn_analysis',
                target_platform='kongfuzi',
                target_isbn="9787544291200",
                priority=9
            )
    
    def test_get_queue_status(self):
        """测试获取队列状态"""
        # Mock各种方法
        with patch.object(self.task_queue.task_repo, 'get_platform_task_count') as mock_count, \
             patch.object(self.task_queue, '_get_today_completed_count') as mock_completed, \
             patch.object(self.task_queue, '_get_today_failed_count') as mock_failed, \
             patch.object(self.task_queue, 'get_recent_tasks') as mock_recent:
            
            # 设置mock返回值
            mock_count.side_effect = lambda platform, status: {
                ('kongfuzi', 'pending'): 5,
                ('kongfuzi', 'running'): 2,
                ('duozhuayu', 'pending'): 3,
                ('duozhuayu', 'running'): 1,
                ('taobao', 'pending'): 0,
                ('taobao', 'running'): 0,
            }.get((platform, status), 0)
            
            mock_completed.side_effect = lambda platform: {
                'kongfuzi': 10, 'duozhuayu': 5, 'taobao': 0
            }.get(platform, 0)
            
            mock_failed.side_effect = lambda platform: {
                'kongfuzi': 2, 'duozhuayu': 1, 'taobao': 0
            }.get(platform, 0)
            
            mock_recent.return_value = [{'id': 1, 'task_name': '测试任务'}]
            
            # 执行测试
            status = self.task_queue.get_queue_status()
            
            # 验证结果
            assert status['total_pending'] == 5  # kongfuzi pending
            assert status['total_running'] == 2   # kongfuzi running
            
            # 验证平台统计
            kongfuzi_stats = status['platform_stats']['kongfuzi']
            assert kongfuzi_stats['pending'] == 5
            assert kongfuzi_stats['running'] == 2
            assert kongfuzi_stats['completed_today'] == 10
            assert kongfuzi_stats['failed_today'] == 2
            
            duozhuayu_stats = status['platform_stats']['duozhuayu']
            assert duozhuayu_stats['pending'] == 3
            assert duozhuayu_stats['running'] == 1
            
            assert status['recent_tasks'] == [{'id': 1, 'task_name': '测试任务'}]
    
    def test_get_pending_tasks(self):
        """测试获取待处理任务"""
        mock_tasks = [
            {'id': 1, 'task_name': '任务1', 'status': 'pending'},
            {'id': 2, 'task_name': '任务2', 'status': 'pending'}
        ]
        
        # 测试获取所有平台的待处理任务
        with patch.object(self.task_queue.task_repo, 'get_pending_tasks') as mock_get:
            mock_get.return_value = mock_tasks
            
            result = self.task_queue.get_pending_tasks()
            assert result == mock_tasks
            mock_get.assert_called_once()
        
        # 测试获取特定平台的待处理任务
        with patch.object(self.task_queue.task_repo, 'get_pending_tasks_by_platform') as mock_get_by_platform:
            mock_get_by_platform.return_value = mock_tasks
            
            result = self.task_queue.get_pending_tasks('kongfuzi')
            assert result == mock_tasks
            mock_get_by_platform.assert_called_once_with('kongfuzi')
    
    def test_get_task_by_id(self):
        """测试根据ID获取任务"""
        mock_task = {'id': 123, 'task_name': '测试任务', 'status': 'pending'}
        
        with patch.object(self.task_queue.task_repo, 'get_by_id') as mock_get:
            mock_get.return_value = mock_task
            
            result = self.task_queue.get_task_by_id(123)
            assert result == mock_task
            mock_get.assert_called_once_with(123)
    
    def test_cancel_task_success(self):
        """测试成功取消任务"""
        mock_task = {'id': 123, 'status': 'pending'}
        
        with patch.object(self.task_queue.task_repo, 'get_by_id') as mock_get, \
             patch.object(self.task_queue.task_repo, 'update_status') as mock_update:
            
            mock_get.return_value = mock_task
            mock_update.return_value = True
            
            result = self.task_queue.cancel_task(123)
            
            assert result is True
            mock_get.assert_called_once_with(123)
            mock_update.assert_called_once_with(123, 'cancelled')
    
    def test_cancel_task_not_found(self):
        """测试取消不存在的任务"""
        with patch.object(self.task_queue.task_repo, 'get_by_id') as mock_get:
            mock_get.return_value = None
            
            result = self.task_queue.cancel_task(999)
            assert result is False
            mock_get.assert_called_once_with(999)
    
    def test_cancel_task_wrong_status(self):
        """测试取消非pending状态的任务"""
        mock_task = {'id': 123, 'status': 'running'}
        
        with patch.object(self.task_queue.task_repo, 'get_by_id') as mock_get:
            mock_get.return_value = mock_task
            
            result = self.task_queue.cancel_task(123)
            assert result is False
            mock_get.assert_called_once_with(123)
    
    def test_retry_failed_tasks_with_platform(self):
        """测试重试特定平台的失败任务"""
        with patch('src.services.simple_task_queue.db') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # 模拟查询结果
            mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]
            mock_cursor.rowcount = 3
            
            result = self.task_queue.retry_failed_tasks('kongfuzi')
            
            assert result == 3
            # 验证SQL调用
            assert mock_cursor.execute.call_count == 2  # SELECT + UPDATE
    
    def test_retry_failed_tasks_all_platforms(self):
        """测试重试所有平台的失败任务"""
        with patch('src.services.simple_task_queue.db') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_cursor.fetchall.return_value = [(1,), (2,)]
            mock_cursor.rowcount = 2
            
            result = self.task_queue.retry_failed_tasks()
            
            assert result == 2
    
    def test_clear_pending_tasks_with_platform(self):
        """测试清空特定平台的待处理任务"""
        with patch('src.services.simple_task_queue.db') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_cursor.rowcount = 5
            
            result = self.task_queue.clear_pending_tasks('kongfuzi')
            
            assert result == 5
            mock_cursor.execute.assert_called_once()
    
    def test_batch_add_isbn_tasks(self):
        """测试批量添加ISBN任务"""
        isbn_list = ["9787544291200", "9787020002207"]
        
        with patch.object(self.task_queue, 'add_book_sales_task') as mock_sales, \
             patch.object(self.task_queue, 'add_price_update_task') as mock_price:
            
            mock_sales.side_effect = [101, 103]  # 返回任务ID
            mock_price.side_effect = [102, 104]
            
            result = self.task_queue.batch_add_isbn_tasks(isbn_list, priority=6)
            
            assert result == [101, 102, 103, 104]
            assert mock_sales.call_count == 2
            assert mock_price.call_count == 2
            
            # 验证调用参数
            mock_sales.assert_any_call("9787544291200", shop_id=1, priority=6)
            mock_sales.assert_any_call("9787020002207", shop_id=1, priority=6)
            mock_price.assert_any_call("9787544291200", shop_id=1, priority=5)  # priority-1
            mock_price.assert_any_call("9787020002207", shop_id=1, priority=5)
    
    def test_cleanup_old_tasks(self):
        """测试清理旧任务"""
        with patch.object(self.task_queue.task_repo, 'cleanup_old_completed_tasks') as mock_cleanup:
            mock_cleanup.return_value = 10
            
            result = self.task_queue.cleanup_old_tasks(7)
            
            assert result == 10
            mock_cleanup.assert_called_once_with(7)
    
    @pytest.mark.asyncio
    async def test_get_today_completed_count(self):
        """测试获取今日完成任务数"""
        with patch('src.services.simple_task_queue.db') as mock_db:
            mock_db.execute_query.return_value = [{'COUNT(*)': 5}]
            
            result = self.task_queue._get_today_completed_count('kongfuzi')
            
            assert result == 5
    
    @pytest.mark.asyncio  
    async def test_get_today_failed_count(self):
        """测试获取今日失败任务数"""
        with patch('src.services.simple_task_queue.db') as mock_db:
            mock_db.execute_query.return_value = [{'COUNT(*)': 3}]
            
            result = self.task_queue._get_today_failed_count('kongfuzi')
            
            assert result == 3
    
    def test_get_today_counts_exception_handling(self):
        """测试今日统计异常处理"""
        with patch('src.services.simple_task_queue.db') as mock_db:
            mock_db.execute_query.side_effect = Exception("数据库错误")
            
            # 异常时应返回0
            completed = self.task_queue._get_today_completed_count('kongfuzi')
            failed = self.task_queue._get_today_failed_count('kongfuzi')
            
            assert completed == 0
            assert failed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])