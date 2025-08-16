#!/usr/bin/env python3
"""
数据仓库层单元测试
测试数据访问层的CRUD操作，重点测试业务逻辑而不是数据库连接
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository, 
    SalesRepository, CrawlTaskRepository, StatisticsRepository
)
from src.models.models import Shop, Book, BookInventory, SalesRecord, CrawlTask


class TestShopRepository:
    """店铺仓库单元测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.repo = ShopRepository()
        self.unique_id = str(uuid.uuid4())[:8]
    
    def test_create_shop_success(self):
        """测试成功创建店铺"""
        shop = Shop(
            shop_id=f"test_shop_{self.unique_id}",
            shop_name="测试店铺",
            platform="kongfuzi",
            shop_url="https://shop123.kongfz.com/"
        )
        
        mock_cursor = Mock()
        mock_cursor.lastrowid = 123
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            
            result = self.repo.create(shop)
            
            assert result == 123
            mock_cursor.execute.assert_called_once()
            # 验证SQL参数
            call_args = mock_cursor.execute.call_args
            assert shop.shop_id in call_args[0][1]
            assert shop.shop_name in call_args[0][1]
    
    def test_get_by_id_found(self):
        """测试根据ID获取店铺 - 找到"""
        shop_id = f"test_shop_{self.unique_id}"
        mock_shop_data = {
            'id': 1,
            'shop_id': shop_id,
            'shop_name': '测试店铺',
            'platform': 'kongfuzi'
        }
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [mock_shop_data]
            
            result = self.repo.get_by_id(shop_id)
            
            assert result == mock_shop_data
            mock_db.execute_query.assert_called_once_with(
                "SELECT * FROM shops WHERE shop_id = ?", (shop_id,)
            )
    
    def test_get_by_id_not_found(self):
        """测试根据ID获取店铺 - 未找到"""
        shop_id = "nonexistent_shop"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = []
            
            result = self.repo.get_by_id(shop_id)
            
            assert result is None
    
    def test_get_all_active(self):
        """测试获取所有活跃店铺"""
        mock_shops = [
            {'id': 1, 'shop_name': '店铺1', 'status': 'active'},
            {'id': 2, 'shop_name': '店铺2', 'status': 'active'}
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = mock_shops
            
            result = self.repo.get_all_active()
            
            assert result == mock_shops
            mock_db.execute_query.assert_called_once_with(
                "SELECT * FROM shops WHERE status = 'active'"
            )
    
    def test_update_status_success(self):
        """测试成功更新店铺状态"""
        shop_id = f"test_shop_{self.unique_id}"
        new_status = "inactive"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 1
            
            result = self.repo.update_status(shop_id, new_status)
            
            assert result is True
            mock_db.execute_update.assert_called_once()
            call_args = mock_db.execute_update.call_args[0]
            assert new_status in call_args[1]
            assert shop_id in call_args[1]
    
    def test_batch_create_shops(self):
        """测试批量创建店铺"""
        shops = [
            Shop(shop_id="shop1", shop_name="店铺1", platform="kongfuzi"),
            Shop(shop_id="shop2", shop_name="店铺2", platform="kongfuzi")
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_many.return_value = 2
            
            result = self.repo.batch_create(shops)
            
            assert result == 2
            mock_db.execute_many.assert_called_once()
            # 验证参数数量
            call_args = mock_db.execute_many.call_args
            assert len(call_args[0][1]) == 2  # 两个店铺的参数


class TestBookRepository:
    """书籍仓库单元测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.repo = BookRepository()
        self.unique_id = str(uuid.uuid4())[:8]
    
    def test_create_or_update_new_book(self):
        """测试创建新书籍"""
        book = Book(
            isbn=f"978{self.unique_id}",
            title="测试书籍",
            author="测试作者",
            publisher="测试出版社"
        )
        
        # Mock不存在的书籍
        with patch.object(self.repo, 'get_by_isbn') as mock_get:
            mock_get.return_value = None
            
            mock_cursor = Mock()
            mock_cursor.rowcount = 1
            mock_conn = Mock()
            mock_conn.cursor.return_value = mock_cursor
            
            with patch('src.models.repositories.db') as mock_db:
                mock_db.get_connection.return_value.__enter__.return_value = mock_conn
                
                result = self.repo.create_or_update(book)
                
                assert result == book.isbn
                mock_cursor.execute.assert_called_once()
                # 验证INSERT语句
                call_args = mock_cursor.execute.call_args[0]
                assert "INSERT OR IGNORE" in call_args[0]
                assert book.isbn in call_args[1]
    
    def test_create_or_update_existing_book(self):
        """测试更新已存在的书籍"""
        isbn = f"978{self.unique_id}"
        book = Book(isbn=isbn, title="测试书籍")
        
        # Mock已存在的书籍
        existing_book = {'isbn': isbn, 'title': '原书籍'}
        with patch.object(self.repo, 'get_by_isbn') as mock_get:
            mock_get.return_value = existing_book
            
            result = self.repo.create_or_update(book)
            
            assert result == isbn
            mock_get.assert_called_once_with(isbn)
    
    def test_get_by_isbn_found(self):
        """测试根据ISBN获取书籍 - 找到"""
        isbn = f"978{self.unique_id}"
        mock_book = {'isbn': isbn, 'title': '测试书籍'}
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [mock_book]
            
            result = self.repo.get_by_isbn(isbn)
            
            assert result == mock_book
            mock_db.execute_query.assert_called_once_with(
                "SELECT * FROM books WHERE isbn = ?", (isbn,)
            )
    
    def test_search_by_title(self):
        """测试根据标题搜索书籍"""
        title = "Python编程"
        mock_books = [
            {'isbn': '123', 'title': 'Python编程入门'},
            {'isbn': '456', 'title': 'Python编程实战'}
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = mock_books
            
            result = self.repo.search_by_title(title)
            
            assert result == mock_books
            mock_db.execute_query.assert_called_once_with(
                "SELECT * FROM books WHERE title LIKE ?", (f"%{title}%",)
            )


class TestBookInventoryRepository:
    """书籍库存仓库单元测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.repo = BookInventoryRepository()
        self.unique_id = str(uuid.uuid4())[:8]
    
    def test_upsert_with_profit_calculation(self):
        """测试插入库存并计算利润"""
        inventory = BookInventory(
            isbn=f"978{self.unique_id}",
            shop_id=1,
            kongfuzi_price=25.0,
            duozhuayu_second_hand_price=30.0
        )
        
        mock_cursor = Mock()
        mock_cursor.lastrowid = 123
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            
            result = self.repo.upsert(inventory)
            
            assert result == 123
            # 验证利润计算
            assert inventory.price_diff_second_hand == 5.0  # 30 - 25
            assert inventory.profit_margin_second_hand == 20.0  # (5/25) * 100
            assert inventory.is_profitable is True
            
            mock_cursor.execute.assert_called_once()
    
    def test_upsert_no_profit(self):
        """测试插入无利润的库存"""
        inventory = BookInventory(
            isbn=f"978{self.unique_id}",
            shop_id=1,
            kongfuzi_price=30.0,
            duozhuayu_second_hand_price=25.0
        )
        
        mock_cursor = Mock()
        mock_cursor.lastrowid = 124
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            
            result = self.repo.upsert(inventory)
            
            assert result == 124
            # 验证无利润
            assert inventory.price_diff_second_hand == -5.0  # 25 - 30
            assert inventory.is_profitable is False
    
    def test_get_by_book_shop(self):
        """测试根据书籍和店铺获取库存"""
        isbn = f"978{self.unique_id}"
        shop_id = 1
        mock_inventory = {
            'isbn': isbn,
            'shop_id': shop_id,
            'kongfuzi_price': 25.0
        }
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [mock_inventory]
            
            result = self.repo.get_by_book_shop(isbn, shop_id)
            
            assert result == mock_inventory
            mock_db.execute_query.assert_called_once_with(
                "SELECT * FROM book_inventory WHERE isbn = ? AND shop_id = ?",
                (isbn, shop_id)
            )
    
    def test_get_profitable_items(self):
        """测试获取有利润的商品"""
        mock_items = [
            {'isbn': '123', 'price_diff_second_hand': 10.0, 'profit_margin_second_hand': 40.0},
            {'isbn': '456', 'price_diff_second_hand': 8.0, 'profit_margin_second_hand': 32.0}
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = mock_items
            
            result = self.repo.get_profitable_items(min_margin=30.0, limit=10)
            
            assert result == mock_items
            call_args = mock_db.execute_query.call_args[0]
            assert 30.0 in call_args[1]  # min_margin参数
            assert 10 in call_args[1]    # limit参数


class TestSalesRepository:
    """销售记录仓库单元测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.repo = SalesRepository()
        self.unique_id = str(uuid.uuid4())[:8]
    
    def test_create_sales_record(self):
        """测试创建销售记录"""
        sale = SalesRecord(
            item_id=f"item_{self.unique_id}",
            isbn=f"978{self.unique_id}",
            shop_id=1,
            sale_price=25.0,
            sale_date=datetime.now()
        )
        
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            
            result = self.repo.create(sale)
            
            assert result == sale.item_id
            mock_cursor.execute.assert_called_once()
            # 验证SQL语句使用INSERT OR IGNORE进行去重
            call_args = mock_cursor.execute.call_args[0]
            assert "INSERT OR IGNORE" in call_args[0]
            assert sale.item_id in call_args[1]
    
    def test_batch_create_sales(self):
        """测试批量创建销售记录"""
        sales = [
            SalesRecord(
                item_id=f"item1_{self.unique_id}",
                isbn=f"978{self.unique_id}",
                shop_id=1,
                sale_price=25.0,
                sale_date=datetime.now()
            ),
            SalesRecord(
                item_id=f"item2_{self.unique_id}",
                isbn=f"978{self.unique_id}",
                shop_id=1,
                sale_price=30.0,
                sale_date=datetime.now()
            )
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_many.return_value = 2
            
            result = self.repo.batch_create(sales)
            
            assert result == 2
            mock_db.execute_many.assert_called_once()
            # 验证参数数量
            call_args = mock_db.execute_many.call_args
            assert len(call_args[0][1]) == 2
    
    def test_get_hot_sales(self):
        """测试获取热销书籍"""
        mock_hot_sales = [
            {
                'isbn': '123',
                'title': '热销书1',
                'sale_count': 10,
                'avg_price': 25.0,
                'min_price': 20.0,
                'max_price': 30.0
            },
            {
                'isbn': '456',
                'title': '热销书2',
                'sale_count': 8,
                'avg_price': 35.0,
                'min_price': 30.0,
                'max_price': 40.0
            }
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = mock_hot_sales
            
            result = self.repo.get_hot_sales(days=7, limit=20)
            
            assert result == mock_hot_sales
            call_args = mock_db.execute_query.call_args[0]
            assert 20 in call_args[1]  # limit参数
            assert 0 in call_args[1]   # offset参数
    
    def test_get_price_statistics(self):
        """测试获取价格统计"""
        isbn = f"978{self.unique_id}"
        mock_stats = {
            'avg_price': 25.5,
            'min_price': 20.0,
            'max_price': 30.0,
            'sale_count': 5
        }
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [mock_stats]
            
            result = self.repo.get_price_statistics(isbn, days=30)
            
            assert result == mock_stats
            call_args = mock_db.execute_query.call_args[0]
            assert isbn in call_args[1]
    
    def test_get_price_statistics_no_data(self):
        """测试获取价格统计 - 无数据"""
        isbn = "nonexistent_isbn"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = []
            
            result = self.repo.get_price_statistics(isbn)
            
            expected = {'avg_price': 0, 'min_price': 0, 'max_price': 0, 'sale_count': 0}
            assert result == expected


class TestCrawlTaskRepository:
    """爬虫任务仓库单元测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.repo = CrawlTaskRepository()
        self.unique_id = str(uuid.uuid4())[:8]
    
    def test_create_crawl_task(self):
        """测试创建爬虫任务"""
        task = CrawlTask(
            task_name=f"测试任务_{self.unique_id}",
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            target_isbn=f"978{self.unique_id}",
            priority=5,
            task_params={"max_pages": 10}
        )
        
        mock_cursor = Mock()
        mock_cursor.lastrowid = 123
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.get_connection.return_value.__enter__.return_value = mock_conn
            
            result = self.repo.create(task)
            
            assert result == 123
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            assert task.task_name in call_args[1]
            assert task.target_isbn in call_args[1]
    
    def test_update_status_to_running(self):
        """测试更新任务状态为运行中"""
        task_id = 123
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 1
            
            result = self.repo.update_status(task_id, 'running', progress=10.0)
            
            assert result is True
            call_args = mock_db.execute_update.call_args[0]
            assert 'running' in call_args[1]
            assert 10.0 in call_args[1]
            assert task_id in call_args[1]
    
    def test_update_status_to_completed(self):
        """测试更新任务状态为已完成"""
        task_id = 123
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 1
            
            result = self.repo.update_status(task_id, 'completed', progress=100.0)
            
            assert result is True
            call_args = mock_db.execute_update.call_args[0]
            assert 'completed' in call_args[1]
            assert 100.0 in call_args[1]
            # 验证SQL包含end_time更新
            assert "end_time" in call_args[0][0]
    
    def test_get_pending_tasks(self):
        """测试获取待处理任务"""
        mock_tasks = [
            {'id': 1, 'task_name': '任务1', 'status': 'pending', 'priority': 5},
            {'id': 2, 'task_name': '任务2', 'status': 'pending', 'priority': 7}
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = mock_tasks
            
            result = self.repo.get_pending_tasks()
            
            assert result == mock_tasks
            call_args = mock_db.execute_query.call_args[0]
            assert "status = 'pending'" in call_args[0]
            assert "ORDER BY priority DESC" in call_args[0]
    
    def test_get_pending_tasks_by_platform(self):
        """测试获取指定平台的待处理任务"""
        platform = "kongfuzi"
        mock_tasks = [
            {'id': 1, 'target_platform': platform, 'status': 'pending'}
        ]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = mock_tasks
            
            result = self.repo.get_pending_tasks_by_platform(platform)
            
            assert result == mock_tasks
            call_args = mock_db.execute_query.call_args[0]
            assert platform in call_args[1]
    
    def test_get_platform_task_count_with_status(self):
        """测试获取指定平台和状态的任务数量"""
        platform = "kongfuzi"
        status = "pending"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [{'COUNT(*)': 5}]
            
            result = self.repo.get_platform_task_count(platform, status)
            
            assert result == 5
            call_args = mock_db.execute_query.call_args[0]
            assert platform in call_args[1]
            assert status in call_args[1]
    
    def test_get_platform_task_count_all_status(self):
        """测试获取指定平台所有状态的任务数量"""
        platform = "kongfuzi"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [{'COUNT(*)': 10}]
            
            result = self.repo.get_platform_task_count(platform)
            
            assert result == 10
            call_args = mock_db.execute_query.call_args[0]
            assert platform in call_args[1]
            assert len(call_args[1]) == 1  # 只有platform参数，没有status
    
    def test_cleanup_old_completed_tasks(self):
        """测试清理旧的已完成任务"""
        days_old = 7
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 3
            
            result = self.repo.cleanup_old_completed_tasks(days_old)
            
            assert result == 3
            call_args = mock_db.execute_update.call_args[0]
            assert "status = 'completed'" in call_args[0]
            assert f"-{days_old} days" in call_args[0]
    
    def test_batch_delete_tasks(self):
        """测试批量删除任务"""
        task_ids = [1, 2, 3]
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 3
            
            result = self.repo.batch_delete(task_ids)
            
            assert result == 3
            call_args = mock_db.execute_update.call_args[0]
            assert "DELETE FROM crawl_tasks" in call_args[0]
            assert "WHERE id IN" in call_args[0]
            assert tuple(task_ids) == call_args[1]
    
    def test_batch_delete_empty_list(self):
        """测试批量删除空任务列表"""
        result = self.repo.batch_delete([])
        assert result == 0


class TestStatisticsRepository:
    """统计数据仓库单元测试"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.repo = StatisticsRepository()
    
    def test_calculate_and_save_statistics_daily(self):
        """测试计算并保存日统计"""
        stat_type = "sales"
        stat_period = "daily"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 1
            
            self.repo.calculate_and_save_statistics(stat_type, stat_period)
            
            mock_db.execute_update.assert_called_once()
            call_args = mock_db.execute_update.call_args[0]
            assert "INSERT OR REPLACE" in call_args[0]
            assert stat_type in call_args[1]
            assert stat_period in call_args[1]
            assert "-1 days" in call_args[0]  # daily统计使用1天
    
    def test_calculate_and_save_statistics_weekly(self):
        """测试计算并保存周统计"""
        stat_type = "sales"
        stat_period = "weekly"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_update.return_value = 1
            
            self.repo.calculate_and_save_statistics(stat_type, stat_period)
            
            call_args = mock_db.execute_update.call_args[0]
            assert "-7 days" in call_args[0]  # weekly统计使用7天
    
    def test_get_statistics_found(self):
        """测试获取统计数据 - 找到"""
        stat_type = "sales"
        stat_period = "daily"
        mock_stats = {
            'stat_type': stat_type,
            'stat_period': stat_period,
            'total_sales': 100,
            'total_revenue': 2500.0,
            'avg_price': 25.0
        }
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = [mock_stats]
            
            result = self.repo.get_statistics(stat_type, stat_period)
            
            assert result == mock_stats
            call_args = mock_db.execute_query.call_args[0]
            assert stat_type in call_args[1]
            assert stat_period in call_args[1]
    
    def test_get_statistics_not_found(self):
        """测试获取统计数据 - 未找到"""
        stat_type = "sales"
        stat_period = "daily"
        
        with patch('src.models.repositories.db') as mock_db:
            mock_db.execute_query.return_value = []
            
            result = self.repo.get_statistics(stat_type, stat_period)
            
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])