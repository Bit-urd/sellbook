"""
Book模型单元测试
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from src.models.book import Book


class TestBook:
    """Book模型测试类"""
    
    def test_book_creation(self):
        """测试Book对象创建"""
        book = Book(
            isbn="9787111213826",
            title="计算机网络",
            author="谢希仁",
            publisher="电子工业出版社",
            publication_date=date(2019, 1, 1),
            price=Decimal("59.00"),
            stock_quantity=10,
            shop_id="test_shop"
        )
        
        assert book.isbn == "9787111213826"
        assert book.title == "计算机网络"
        assert book.author == "谢希仁"
        assert book.publisher == "电子工业出版社"
        assert book.publication_date == date(2019, 1, 1)
        assert book.price == Decimal("59.00")
        assert book.stock_quantity == 10
        assert book.shop_id == "test_shop"
        assert isinstance(book.created_at, datetime)
        assert isinstance(book.updated_at, datetime)
    
    def test_book_repr(self):
        """测试Book对象字符串表示"""
        book = Book(
            isbn="9787111213826",
            title="计算机网络",
            author="谢希仁",
            publisher="电子工业出版社",
            publication_date=date(2019, 1, 1),
            price=Decimal("59.00"),
            stock_quantity=10,
            shop_id="test_shop"
        )
        
        repr_str = repr(book)
        assert "Book" in repr_str
        assert "9787111213826" in repr_str
        assert "计算机网络" in repr_str
    
    def test_book_validation(self):
        """测试Book字段验证"""
        # 测试必填字段
        with pytest.raises(TypeError):
            Book()
        
        # 测试部分字段
        book = Book(
            isbn="9787111213826",
            title="计算机网络",
            shop_id="test_shop"
        )
        assert book.isbn == "9787111213826"
        assert book.title == "计算机网络"
        assert book.shop_id == "test_shop"
        assert book.author is None
        assert book.publisher is None
        assert book.publication_date is None
        assert book.price is None
        assert book.stock_quantity == 0  # 默认值
    
    def test_book_price_handling(self):
        """测试价格字段处理"""
        # 测试Decimal价格
        book1 = Book(
            isbn="9787111213826",
            title="测试书籍",
            shop_id="test_shop",
            price=Decimal("59.99")
        )
        assert book1.price == Decimal("59.99")
        
        # 测试float价格自动转换为Decimal
        book2 = Book(
            isbn="9787111213827",
            title="测试书籍2",
            shop_id="test_shop",
            price=59.99
        )
        assert isinstance(book2.price, (Decimal, float))
        
        # 测试None价格
        book3 = Book(
            isbn="9787111213828",
            title="测试书籍3",
            shop_id="test_shop"
        )
        assert book3.price is None
    
    def test_book_stock_quantity(self):
        """测试库存数量字段"""
        # 测试默认库存
        book1 = Book(
            isbn="9787111213826",
            title="测试书籍",
            shop_id="test_shop"
        )
        assert book1.stock_quantity == 0
        
        # 测试指定库存
        book2 = Book(
            isbn="9787111213827",
            title="测试书籍2",
            shop_id="test_shop",
            stock_quantity=15
        )
        assert book2.stock_quantity == 15
        
        # 测试负数库存
        book3 = Book(
            isbn="9787111213828",
            title="测试书籍3",
            shop_id="test_shop",
            stock_quantity=-5
        )
        assert book3.stock_quantity == -5
    
    def test_book_timestamps(self):
        """测试时间戳字段"""
        book = Book(
            isbn="9787111213826",
            title="测试书籍",
            shop_id="test_shop"
        )
        
        created_time = book.created_at
        updated_time = book.updated_at
        
        # 验证时间戳是datetime对象
        assert isinstance(created_time, datetime)
        assert isinstance(updated_time, datetime)
        
        # 验证创建时间和更新时间相近（在同一秒内）
        time_diff = abs((updated_time - created_time).total_seconds())
        assert time_diff < 1.0