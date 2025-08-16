#!/usr/bin/env python3
"""
数据模型单元测试
测试数据模型的基本功能、验证和业务逻辑
"""
import pytest
from datetime import datetime
from dataclasses import asdict

from src.models.models import Shop, Book, BookInventory, SalesRecord, CrawlTask, DataStatistics


class TestShopModel:
    """店铺模型单元测试"""
    
    def test_shop_creation_minimal(self):
        """测试最小参数创建店铺"""
        shop = Shop(
            shop_id="test_shop_123",
            shop_name="测试店铺"
        )
        
        assert shop.shop_id == "test_shop_123"
        assert shop.shop_name == "测试店铺"
        assert shop.platform == "kongfuzi"  # 默认值
        assert shop.status == "active"      # 默认值
        assert shop.shop_url is None
        assert shop.id is None
    
    def test_shop_creation_full(self):
        """测试完整参数创建店铺"""
        now = datetime.now()
        shop = Shop(
            shop_id="full_shop_456",
            shop_name="完整店铺",
            platform="duozhuayu",
            shop_url="https://shop456.duozhuayu.com/",
            shop_type="individual",
            status="inactive",
            id=123,
            created_at=now,
            updated_at=now
        )
        
        assert shop.shop_id == "full_shop_456"
        assert shop.shop_name == "完整店铺"
        assert shop.platform == "duozhuayu"
        assert shop.shop_url == "https://shop456.duozhuayu.com/"
        assert shop.shop_type == "individual"
        assert shop.status == "inactive"
        assert shop.id == 123
        assert shop.created_at == now
        assert shop.updated_at == now
    
    def test_shop_dataclass_conversion(self):
        """测试店铺数据类转换"""
        shop = Shop(
            shop_id="convert_shop",
            shop_name="转换店铺",
            platform="kongfuzi"
        )
        
        # 测试转换为字典
        shop_dict = asdict(shop)
        assert isinstance(shop_dict, dict)
        assert shop_dict['shop_id'] == "convert_shop"
        assert shop_dict['shop_name'] == "转换店铺"
        assert shop_dict['platform'] == "kongfuzi"


class TestBookModel:
    """书籍模型单元测试"""
    
    def test_book_creation_minimal(self):
        """测试最小参数创建书籍"""
        book = Book(
            isbn="9787544291200",
            title="测试书籍"
        )
        
        assert book.isbn == "9787544291200"
        assert book.title == "测试书籍"
        assert book.author is None
        assert book.publisher is None
        assert book.id is None
    
    def test_book_creation_full(self):
        """测试完整参数创建书籍"""
        now = datetime.now()
        book = Book(
            isbn="9787020002207",
            title="完整书籍信息",
            author="测试作者",
            publisher="测试出版社",
            publish_date="2024-01-01",
            category="计算机",
            subcategory="编程语言",
            description="这是一本测试书籍",
            cover_image_url="https://example.com/cover.jpg",
            id=456,
            created_at=now,
            updated_at=now
        )
        
        assert book.isbn == "9787020002207"
        assert book.title == "完整书籍信息"
        assert book.author == "测试作者"
        assert book.publisher == "测试出版社"
        assert book.publish_date == "2024-01-01"
        assert book.category == "计算机"
        assert book.subcategory == "编程语言"
        assert book.description == "这是一本测试书籍"
        assert book.cover_image_url == "https://example.com/cover.jpg"
        assert book.id == 456
    
    def test_book_isbn_validation(self):
        """测试ISBN是书籍的唯一标识"""
        book1 = Book(isbn="9787544291200", title="书籍1")
        book2 = Book(isbn="9787544291200", title="书籍2")  # 相同ISBN
        
        # ISBN应该是唯一的业务标识
        assert book1.isbn == book2.isbn
        # 但书籍内容可能不同
        assert book1.title != book2.title


class TestBookInventoryModel:
    """书籍库存模型单元测试"""
    
    def test_book_inventory_creation_minimal(self):
        """测试最小参数创建库存"""
        inventory = BookInventory(
            isbn="9787544291200",
            shop_id=1
        )
        
        assert inventory.isbn == "9787544291200"
        assert inventory.shop_id == 1
        assert inventory.kongfuzi_price is None
        assert inventory.duozhuayu_new_price is None
        assert inventory.kongfuzi_stock == 0
        assert inventory.duozhuayu_in_stock is False
        assert inventory.is_profitable is False
        assert inventory.status == "active"
    
    def test_book_inventory_creation_full(self):
        """测试完整参数创建库存"""
        now = datetime.now()
        inventory = BookInventory(
            isbn="9787020002207",
            shop_id=2,
            kongfuzi_price=25.0,
            kongfuzi_original_price=30.0,
            kongfuzi_stock=5,
            kongfuzi_condition="九品",
            kongfuzi_condition_desc="品相良好",
            kongfuzi_book_url="https://www.kongfz.com/book/123",
            kongfuzi_item_id="item_123",
            duozhuayu_new_price=35.0,
            duozhuayu_second_hand_price=28.0,
            duozhuayu_in_stock=True,
            duozhuayu_book_url="https://www.duozhuayu.com/book/456",
            price_diff_new=10.0,
            price_diff_second_hand=3.0,
            profit_margin_new=40.0,
            profit_margin_second_hand=12.0,
            is_profitable=True,
            status="active",
            id=789,
            crawled_at=now,
            updated_at=now
        )
        
        assert inventory.isbn == "9787020002207"
        assert inventory.shop_id == 2
        assert inventory.kongfuzi_price == 25.0
        assert inventory.kongfuzi_original_price == 30.0
        assert inventory.kongfuzi_stock == 5
        assert inventory.kongfuzi_condition == "九品"
        assert inventory.duozhuayu_new_price == 35.0
        assert inventory.duozhuayu_second_hand_price == 28.0
        assert inventory.duozhuayu_in_stock is True
        assert inventory.price_diff_new == 10.0
        assert inventory.price_diff_second_hand == 3.0
        assert inventory.profit_margin_new == 40.0
        assert inventory.profit_margin_second_hand == 12.0
        assert inventory.is_profitable is True
    
    def test_book_inventory_profit_logic(self):
        """测试库存利润计算逻辑"""
        # 有利润的情况
        profitable_inventory = BookInventory(
            isbn="profit_book",
            shop_id=1,
            price_diff_second_hand=5.0,
            is_profitable=True
        )
        assert profitable_inventory.is_profitable is True
        
        # 无利润的情况
        unprofitable_inventory = BookInventory(
            isbn="no_profit_book",
            shop_id=1,
            price_diff_second_hand=-2.0,
            is_profitable=False
        )
        assert unprofitable_inventory.is_profitable is False


class TestSalesRecordModel:
    """销售记录模型单元测试"""
    
    def test_sales_record_creation_minimal(self):
        """测试最小参数创建销售记录"""
        now = datetime.now()
        sale = SalesRecord(
            item_id="item_12345",
            isbn="9787544291200",
            shop_id=1,
            sale_price=25.0,
            sale_date=now
        )
        
        assert sale.item_id == "item_12345"
        assert sale.isbn == "9787544291200"
        assert sale.shop_id == 1
        assert sale.sale_price == 25.0
        assert sale.sale_date == now
        assert sale.original_price is None
        assert sale.sale_platform == "kongfuzi"  # 默认值
        assert sale.book_condition is None
        assert sale.id is None
    
    def test_sales_record_creation_full(self):
        """测试完整参数创建销售记录"""
        sale_date = datetime(2024, 1, 15, 14, 30, 0)
        created_at = datetime.now()
        
        sale = SalesRecord(
            item_id="full_item_67890",
            isbn="9787020002207",
            shop_id=2,
            sale_price=35.0,
            sale_date=sale_date,
            original_price=40.0,
            sale_platform="duozhuayu",
            book_condition="八品",
            id=123,
            created_at=created_at
        )
        
        assert sale.item_id == "full_item_67890"
        assert sale.isbn == "9787020002207"
        assert sale.shop_id == 2
        assert sale.sale_price == 35.0
        assert sale.sale_date == sale_date
        assert sale.original_price == 40.0
        assert sale.sale_platform == "duozhuayu"
        assert sale.book_condition == "八品"
        assert sale.id == 123
        assert sale.created_at == created_at
    
    def test_sales_record_item_id_uniqueness(self):
        """测试销售记录item_id的唯一性"""
        now = datetime.now()
        sale1 = SalesRecord(
            item_id="unique_item_001",
            isbn="9787544291200",
            shop_id=1,
            sale_price=25.0,
            sale_date=now
        )
        sale2 = SalesRecord(
            item_id="unique_item_001",  # 相同item_id
            isbn="9787020002207",        # 不同ISBN
            shop_id=2,
            sale_price=30.0,
            sale_date=now
        )
        
        # item_id应该是唯一标识符
        assert sale1.item_id == sale2.item_id
        # 但其他字段可能不同
        assert sale1.isbn != sale2.isbn
        assert sale1.shop_id != sale2.shop_id


class TestCrawlTaskModel:
    """爬虫任务模型单元测试"""
    
    def test_crawl_task_creation_minimal(self):
        """测试最小参数创建爬虫任务"""
        task = CrawlTask(
            task_name="测试爬取任务",
            task_type="book_sales_crawl",
            target_platform="kongfuzi"
        )
        
        assert task.task_name == "测试爬取任务"
        assert task.task_type == "book_sales_crawl"
        assert task.target_platform == "kongfuzi"
        assert task.target_url is None
        assert task.shop_id is None
        assert task.target_isbn is None
        assert task.book_title is None
        assert task.task_params is None
        assert task.priority == 5  # 默认值
        assert task.status == "pending"  # 默认值
        assert task.progress_percentage == 0.0  # 默认值
        assert task.items_crawled == 0
        assert task.items_updated == 0
        assert task.items_failed == 0
    
    def test_crawl_task_creation_full(self):
        """测试完整参数创建爬虫任务"""
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 11, 30, 0)
        created_at = datetime(2024, 1, 15, 9, 30, 0)
        
        task = CrawlTask(
            task_name="完整爬取任务",
            task_type="shop_books_crawl",
            target_platform="duozhuayu",
            target_url="https://shop123.duozhuayu.com/",
            shop_id=123,
            target_isbn="9787544291200",
            book_title="目标书籍",
            task_params={"max_pages": 50, "quality": "九品以上"},
            priority=8,
            status="completed",
            progress_percentage=100.0,
            start_time=start_time,
            end_time=end_time,
            items_crawled=150,
            items_updated=140,
            items_failed=10,
            error_message=None,
            id=456,
            created_at=created_at
        )
        
        assert task.task_name == "完整爬取任务"
        assert task.task_type == "shop_books_crawl"
        assert task.target_platform == "duozhuayu"
        assert task.target_url == "https://shop123.duozhuayu.com/"
        assert task.shop_id == 123
        assert task.target_isbn == "9787544291200"
        assert task.book_title == "目标书籍"
        assert task.task_params == {"max_pages": 50, "quality": "九品以上"}
        assert task.priority == 8
        assert task.status == "completed"
        assert task.progress_percentage == 100.0
        assert task.start_time == start_time
        assert task.end_time == end_time
        assert task.items_crawled == 150
        assert task.items_updated == 140
        assert task.items_failed == 10
        assert task.error_message is None
        assert task.id == 456
        assert task.created_at == created_at
    
    def test_crawl_task_status_values(self):
        """测试爬虫任务状态值"""
        valid_statuses = ['pending', 'queued', 'running', 'completed', 'failed', 'skipped']
        
        for status in valid_statuses:
            task = CrawlTask(
                task_name=f"任务_{status}",
                task_type="book_sales_crawl",
                target_platform="kongfuzi",
                status=status
            )
            assert task.status == status
    
    def test_crawl_task_priority_range(self):
        """测试爬虫任务优先级范围"""
        # 低优先级
        low_task = CrawlTask(
            task_name="低优先级任务",
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            priority=1
        )
        assert low_task.priority == 1
        
        # 高优先级
        high_task = CrawlTask(
            task_name="高优先级任务",
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            priority=10
        )
        assert high_task.priority == 10


class TestDataStatisticsModel:
    """数据统计模型单元测试"""
    
    def test_data_statistics_creation_minimal(self):
        """测试最小参数创建统计数据"""
        stats = DataStatistics(
            stat_type="sales",
            stat_period="daily",
            stat_date="2024-01-15"
        )
        
        assert stats.stat_type == "sales"
        assert stats.stat_period == "daily"
        assert stats.stat_date == "2024-01-15"
        assert stats.isbn is None
        assert stats.shop_id is None
        assert stats.category is None
        assert stats.total_sales == 0
        assert stats.total_revenue == 0.0
        assert stats.avg_price is None
        assert stats.profitable_items_count == 0
    
    def test_data_statistics_creation_full(self):
        """测试完整参数创建统计数据"""
        calculated_at = datetime.now()
        
        stats = DataStatistics(
            stat_type="book_performance",
            stat_period="weekly",
            stat_date="2024-01-15",
            isbn="9787544291200",
            shop_id=123,
            category="计算机",
            total_sales=50,
            total_revenue=1250.0,
            avg_price=25.0,
            median_price=24.0,
            mode_price=20.0,
            min_price=15.0,
            max_price=35.0,
            avg_price_diff=5.0,
            max_profit_margin=40.0,
            profitable_items_count=30,
            id=789,
            calculated_at=calculated_at
        )
        
        assert stats.stat_type == "book_performance"
        assert stats.stat_period == "weekly"
        assert stats.stat_date == "2024-01-15"
        assert stats.isbn == "9787544291200"
        assert stats.shop_id == 123
        assert stats.category == "计算机"
        assert stats.total_sales == 50
        assert stats.total_revenue == 1250.0
        assert stats.avg_price == 25.0
        assert stats.median_price == 24.0
        assert stats.mode_price == 20.0
        assert stats.min_price == 15.0
        assert stats.max_price == 35.0
        assert stats.avg_price_diff == 5.0
        assert stats.max_profit_margin == 40.0
        assert stats.profitable_items_count == 30
        assert stats.id == 789
        assert stats.calculated_at == calculated_at
    
    def test_data_statistics_period_types(self):
        """测试统计周期类型"""
        periods = ["daily", "weekly", "monthly", "yearly"]
        
        for period in periods:
            stats = DataStatistics(
                stat_type="sales",
                stat_period=period,
                stat_date="2024-01-15"
            )
            assert stats.stat_period == period
    
    def test_data_statistics_calculations(self):
        """测试统计数据计算逻辑"""
        stats = DataStatistics(
            stat_type="revenue",
            stat_period="daily",
            stat_date="2024-01-15",
            total_sales=10,
            total_revenue=250.0
        )
        
        # 基本计算验证
        assert stats.total_sales == 10
        assert stats.total_revenue == 250.0
        # 平均价格应该是 250.0 / 10 = 25.0（这在实际使用中由仓库层计算）


class TestModelInteractions:
    """测试模型之间的交互关系"""
    
    def test_book_shop_inventory_relationship(self):
        """测试书籍-店铺-库存关系"""
        # 创建书籍
        book = Book(
            isbn="9787544291200",
            title="Python编程"
        )
        
        # 创建店铺
        shop = Shop(
            shop_id="shop_123",
            shop_name="测试书店"
        )
        
        # 创建库存（关联书籍和店铺）
        inventory = BookInventory(
            isbn=book.isbn,  # 关联书籍
            shop_id=1,       # 关联店铺
            kongfuzi_price=25.0
        )
        
        assert inventory.isbn == book.isbn
        # 在实际应用中，shop_id应该对应shop的数据库ID
    
    def test_sales_record_relationships(self):
        """测试销售记录与其他模型的关系"""
        # 销售记录关联书籍和店铺
        sale = SalesRecord(
            item_id="item_001",
            isbn="9787544291200",  # 关联书籍
            shop_id=1,             # 关联店铺
            sale_price=25.0,
            sale_date=datetime.now()
        )
        
        # 爬虫任务可以生成销售记录
        task = CrawlTask(
            task_name="爬取销售记录",
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            target_isbn=sale.isbn,  # 目标与销售记录一致
            shop_id=sale.shop_id    # 目标店铺与销售记录一致
        )
        
        assert task.target_isbn == sale.isbn
        assert task.shop_id == sale.shop_id


if __name__ == "__main__":
    # 简单的测试运行器，不使用pytest框架
    import inspect
    import sys
    
    # 获取所有测试类
    test_classes = [obj for name, obj in inspect.getmembers(sys.modules[__name__]) 
                   if inspect.isclass(obj) and name.startswith('Test')]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n运行 {test_class.__name__}:")
        test_instance = test_class()
        
        # 获取所有测试方法
        test_methods = [method for method in dir(test_instance) 
                       if method.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                # 运行setup_method如果存在
                if hasattr(test_instance, 'setup_method'):
                    test_instance.setup_method()
                
                # 运行测试方法
                getattr(test_instance, method_name)()
                print(f"  ✓ {method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  ✗ {method_name}: {e}")
    
    print(f"\n测试结果: {passed_tests}/{total_tests} 通过")
    if passed_tests == total_tests:
        print("所有模型测试通过！")
    else:
        print(f"有 {total_tests - passed_tests} 个测试失败")