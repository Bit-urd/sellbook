#!/usr/bin/env python3
"""
CrawlerServiceV2业务接口单元测试
测试统一业务入口的功能，重点测试业务逻辑而不是底层实现
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from src.services.crawler_service import CrawlerServiceV2


class TestCrawlerServiceV2:
    """CrawlerServiceV2单元测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        # 创建服务实例（Mock掉底层依赖）
        with patch('src.services.autonomous_session_manager.autonomous_session_manager') as mock_session_manager, \
             patch('src.services.simple_task_queue.simple_task_queue') as mock_task_queue:
            
            self.service = CrawlerServiceV2()
            self.mock_session_manager = mock_session_manager
            self.mock_task_queue = mock_task_queue
    
    @pytest.mark.asyncio
    async def test_stop(self):
        """测试停止服务"""
        self.mock_session_manager.stop = AsyncMock()
        
        await self.service.stop()
        
        self.mock_session_manager.stop.assert_called_once()
    
    def test_add_book_sales_task(self):
        """测试添加书籍销售记录爬取任务"""
        self.mock_task_queue.add_book_sales_task.return_value = 123
        
        result = self.service.add_book_sales_task(
            isbn="9787544291200",
            shop_id=1,
            book_title="测试书籍",
            priority=7
        )
        
        assert result == 123
        self.mock_task_queue.add_book_sales_task.assert_called_once_with(
            "9787544291200", 1, "测试书籍", 7
        )
    
    def test_add_book_sales_task_with_defaults(self):
        """测试使用默认参数添加书籍销售任务"""
        self.mock_task_queue.add_book_sales_task.return_value = 124
        
        result = self.service.add_book_sales_task("9787544291200")
        
        assert result == 124
        self.mock_task_queue.add_book_sales_task.assert_called_once_with(
            "9787544291200", 1, None, 5  # 默认值
        )
    
    def test_add_shop_books_task(self):
        """测试添加店铺书籍列表爬取任务"""
        self.mock_task_queue.add_shop_books_task.return_value = 125
        
        result = self.service.add_shop_books_task(
            shop_url="https://shop123.kongfz.com/",
            shop_id=2,
            max_pages=20,
            priority=6
        )
        
        assert result == 125
        self.mock_task_queue.add_shop_books_task.assert_called_once_with(
            "https://shop123.kongfz.com/", 2, 20, 6
        )
    
    def test_add_price_update_task(self):
        """测试添加价格更新任务"""
        self.mock_task_queue.add_price_update_task.return_value = 126
        
        result = self.service.add_price_update_task(
            isbn="9787544291200",
            shop_id=3,
            priority=4
        )
        
        assert result == 126
        self.mock_task_queue.add_price_update_task.assert_called_once_with(
            "9787544291200", 3, 4
        )
    
    def test_add_isbn_analysis_task(self):
        """测试添加ISBN分析任务"""
        self.mock_task_queue.add_isbn_analysis_task.return_value = 127
        
        result = self.service.add_isbn_analysis_task(
            isbn="9787544291200",
            priority=9
        )
        
        assert result == 127
        self.mock_task_queue.add_isbn_analysis_task.assert_called_once_with(
            "9787544291200", 9
        )
    
    def test_batch_add_isbn_tasks(self):
        """测试批量添加ISBN任务"""
        isbn_list = ["9787544291200", "9787020002207"]
        self.mock_task_queue.batch_add_isbn_tasks.return_value = [101, 102, 103, 104]
        
        result = self.service.batch_add_isbn_tasks(isbn_list, priority=6)
        
        assert result == [101, 102, 103, 104]
        self.mock_task_queue.batch_add_isbn_tasks.assert_called_once_with(
            isbn_list, 6
        )
    
    @pytest.mark.asyncio
    async def test_get_queue_status(self):
        """测试获取队列状态"""
        # Mock返回值
        mock_task_status = {
            "total_pending": 5,
            "total_running": 2,
            "platform_stats": {"kongfuzi": {"pending": 3}}
        }
        mock_session_status = {
            "running": True,
            "connected": True,
            "total_windows": 3
        }
        
        self.mock_task_queue.get_queue_status.return_value = mock_task_status
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_session_status)
        
        result = await self.service.get_queue_status()
        
        assert result["task_queue"] == mock_task_status
        assert result["session_manager"] == mock_session_status
        self.mock_task_queue.get_queue_status.assert_called_once()
        self.mock_session_manager.get_status.assert_called_once()
    
    def test_get_recent_tasks(self):
        """测试获取最近任务"""
        mock_tasks = [
            {"id": 1, "task_name": "任务1"},
            {"id": 2, "task_name": "任务2"}
        ]
        self.mock_task_queue.get_recent_tasks.return_value = mock_tasks
        
        result = self.service.get_recent_tasks(10)
        
        assert result == mock_tasks
        self.mock_task_queue.get_recent_tasks.assert_called_once_with(10)
    
    def test_get_pending_tasks(self):
        """测试获取待处理任务"""
        mock_tasks = [{"id": 1, "status": "pending"}]
        
        # 测试无平台参数
        self.mock_task_queue.get_pending_tasks.return_value = mock_tasks
        result = self.service.get_pending_tasks()
        assert result == mock_tasks
        self.mock_task_queue.get_pending_tasks.assert_called_once_with(None)
        
        # 测试有平台参数
        self.mock_task_queue.get_pending_tasks.reset_mock()
        result = self.service.get_pending_tasks("kongfuzi")
        self.mock_task_queue.get_pending_tasks.assert_called_once_with("kongfuzi")
    
    def test_get_task_by_id(self):
        """测试根据ID获取任务"""
        mock_task = {"id": 123, "task_name": "测试任务"}
        self.mock_task_queue.get_task_by_id.return_value = mock_task
        
        result = self.service.get_task_by_id(123)
        
        assert result == mock_task
        self.mock_task_queue.get_task_by_id.assert_called_once_with(123)
    
    def test_cancel_task(self):
        """测试取消任务"""
        self.mock_task_queue.cancel_task.return_value = True
        
        result = self.service.cancel_task(123)
        
        assert result is True
        self.mock_task_queue.cancel_task.assert_called_once_with(123)
    
    def test_retry_failed_tasks(self):
        """测试重试失败任务"""
        self.mock_task_queue.retry_failed_tasks.return_value = 5
        
        # 测试无平台参数
        result = self.service.retry_failed_tasks()
        assert result == 5
        self.mock_task_queue.retry_failed_tasks.assert_called_once_with(None)
        
        # 测试有平台参数
        self.mock_task_queue.retry_failed_tasks.reset_mock()
        result = self.service.retry_failed_tasks("kongfuzi")
        self.mock_task_queue.retry_failed_tasks.assert_called_once_with("kongfuzi")
    
    def test_clear_pending_tasks(self):
        """测试清空待处理任务"""
        self.mock_task_queue.clear_pending_tasks.return_value = 10
        
        result = self.service.clear_pending_tasks("kongfuzi")
        
        assert result == 10
        self.mock_task_queue.clear_pending_tasks.assert_called_once_with("kongfuzi")
    
    def test_cleanup_old_tasks(self):
        """测试清理旧任务"""
        self.mock_task_queue.cleanup_old_tasks.return_value = 3
        
        result = self.service.cleanup_old_tasks(7)
        
        assert result == 3
        self.mock_task_queue.cleanup_old_tasks.assert_called_once_with(7)
    
    @pytest.mark.asyncio
    async def test_get_window_status(self):
        """测试获取窗口状态"""
        mock_status = {
            "total_windows": 3,
            "available_windows": 2,
            "busy_windows": 1,
            "available_by_platform": {"kongfuzi": 2},
            "sessions": [{"window_id": "win1"}]
        }
        
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_status)
        
        result = await self.service.get_window_status()
        
        expected = {
            "total_windows": 3,
            "available_windows": 2,
            "busy_windows": 1,
            "available_by_platform": {"kongfuzi": 2},
            "sessions": [{"window_id": "win1"}]
        }
        assert result == expected
        self.mock_session_manager.get_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_platform_status(self):
        """测试获取特定平台状态"""
        mock_session_status = {
            "available_by_platform": {"kongfuzi": 2, "duozhuayu": 1}
        }
        mock_task_status = {
            "platform_stats": {
                "kongfuzi": {
                    "pending": 5,
                    "running": 2,
                    "completed_today": 10,
                    "failed_today": 1
                }
            }
        }
        
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_session_status)
        self.mock_task_queue.get_queue_status.return_value = mock_task_status
        
        result = await self.service.get_platform_status("kongfuzi")
        
        expected = {
            "platform": "kongfuzi",
            "available_windows": 2,
            "pending_tasks": 5,
            "running_tasks": 2,
            "completed_today": 10,
            "failed_today": 1
        }
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """测试获取统计信息"""
        mock_status = {
            "statistics": {
                "tasks_processed": 100,
                "tasks_completed": 90,
                "tasks_failed": 10
            }
        }
        
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_status)
        
        result = await self.service.get_statistics()
        
        assert result == mock_status["statistics"]
        self.mock_session_manager.get_status.assert_called_once()
    
    def test_quick_crawl_isbn(self):
        """测试快速爬取ISBN"""
        self.mock_task_queue.add_book_sales_task.return_value = 101
        self.mock_task_queue.add_price_update_task.return_value = 102
        self.mock_task_queue.add_isbn_analysis_task.return_value = 103
        
        # 测试包含分析任务
        result = self.service.quick_crawl_isbn("9787544291200", include_analysis=True)
        
        assert result == [101, 102, 103]
        
        # 验证调用
        self.mock_task_queue.add_book_sales_task.assert_called_once_with(
            "9787544291200", shop_id=1, book_title=None, priority=8
        )
        self.mock_task_queue.add_price_update_task.assert_called_once_with(
            "9787544291200", shop_id=1, priority=6
        )
        self.mock_task_queue.add_isbn_analysis_task.assert_called_once_with(
            "9787544291200", priority=9
        )
    
    def test_quick_crawl_isbn_without_analysis(self):
        """测试快速爬取ISBN不包含分析"""
        self.mock_task_queue.add_book_sales_task.return_value = 101
        self.mock_task_queue.add_price_update_task.return_value = 102
        
        result = self.service.quick_crawl_isbn("9787544291200", include_analysis=False)
        
        assert result == [101, 102]
        
        # 确保没有调用分析任务
        self.mock_task_queue.add_isbn_analysis_task.assert_not_called()
    
    def test_emergency_stop_platform(self):
        """测试紧急停止平台"""
        self.mock_task_queue.clear_pending_tasks.return_value = 15
        
        result = self.service.emergency_stop_platform("kongfuzi")
        
        expected = {
            "platform": "kongfuzi",
            "cleared_tasks": 15
        }
        assert result == expected
        self.mock_task_queue.clear_pending_tasks.assert_called_once_with("kongfuzi")
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """测试健康检查 - 健康状态"""
        mock_status = {
            "running": True,
            "connected": True,
            "total_windows": 3,
            "available_windows": 2
        }
        
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_status)
        
        result = await self.service.health_check()
        
        expected = {
            "session_manager_running": True,
            "browser_connected": True,
            "total_windows": 3,
            "available_windows": 2,
            "healthy": True,
            "issues": []
        }
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """测试健康检查 - 不健康状态"""
        mock_status = {
            "running": False,
            "connected": False,
            "total_windows": 3,
            "available_windows": 0
        }
        
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_status)
        
        result = await self.service.health_check()
        
        assert result["healthy"] is False
        assert "会话管理器未运行" in result["issues"]
        assert "浏览器未连接" in result["issues"]
        assert "没有可用窗口" in result["issues"]
        assert len(result["issues"]) == 3
    
    @pytest.mark.asyncio
    async def test_health_check_partial_issues(self):
        """测试健康检查 - 部分问题"""
        mock_status = {
            "running": True,
            "connected": True,
            "total_windows": 3,
            "available_windows": 0  # 只有这个问题
        }
        
        self.mock_session_manager.get_status = AsyncMock(return_value=mock_status)
        
        result = await self.service.health_check()
        
        assert result["healthy"] is False
        assert len(result["issues"]) == 1
        assert "没有可用窗口" in result["issues"]
    
    def test_service_attributes(self):
        """测试服务属性正确设置"""
        # 确保服务正确引用了底层组件
        assert self.service.session_manager is self.mock_session_manager
        assert self.service.task_queue is self.mock_task_queue


class TestCrawlerServiceV2Integration:
    """CrawlerServiceV2集成相关测试"""
    
    def test_service_initialization_with_real_dependencies(self):
        """测试服务使用真实依赖的初始化"""
        # 这里测试真实依赖的引用是否正确
        with patch('src.services.crawler_service_v2.autonomous_session_manager') as mock_session, \
             patch('src.services.crawler_service_v2.simple_task_queue') as mock_queue:
            
            service = CrawlerServiceV2()
            
            # 验证依赖注入
            assert service.session_manager is mock_session
            assert service.task_queue is mock_queue
    
    def test_method_signatures(self):
        """测试方法签名的正确性"""
        # 验证关键方法的存在和签名
        service = CrawlerServiceV2()
        
        # 检查同步方法
        assert hasattr(service, 'add_book_sales_task')
        assert hasattr(service, 'add_shop_books_task')
        assert hasattr(service, 'add_price_update_task')
        assert hasattr(service, 'add_isbn_analysis_task')
        assert hasattr(service, 'batch_add_isbn_tasks')
        assert hasattr(service, 'quick_crawl_isbn')
        assert hasattr(service, 'emergency_stop_platform')
        
        # 检查异步方法
        assert hasattr(service, 'get_queue_status')
        assert hasattr(service, 'get_window_status')
        assert hasattr(service, 'get_platform_status')
        assert hasattr(service, 'get_statistics')
        assert hasattr(service, 'health_check')
        assert hasattr(service, 'stop')
        
        # 验证异步方法确实是协程
        import inspect
        assert inspect.iscoroutinefunction(service.get_queue_status)
        assert inspect.iscoroutinefunction(service.get_window_status)
        assert inspect.iscoroutinefunction(service.get_platform_status)
        assert inspect.iscoroutinefunction(service.get_statistics)
        assert inspect.iscoroutinefunction(service.health_check)
        assert inspect.iscoroutinefunction(service.stop)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])