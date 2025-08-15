"""
BookRepository单元测试 (适配stub实现)
"""
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.book_repository import BookRepository
from src.models.book import Book


class TestBookRepository:
    """BookRepository测试类"""
    
    @pytest.fixture
    def mock_session(self):
        """模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def book_repository(self, mock_session):
        """创建BookRepository实例"""
        return BookRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_create_book(self, book_repository):
        """测试创建书籍"""
        book_data = {
            "isbn": "9787111111111",
            "title": "测试书籍",
            "shop_id": "test_shop"
        }
        
        result = await book_repository.create(book_data)
        
        # 验证返回值
        assert isinstance(result, Book)
        assert result.isbn == book_data["isbn"]
        assert result.title == book_data["title"]
    
    @pytest.mark.asyncio
    async def test_get_book_by_isbn_returns_none(self, book_repository):
        """测试获取书籍返回None (stub实现)"""
        result = await book_repository.get_by_isbn("any_isbn")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_books_by_shop_id_returns_empty_list(self, book_repository):
        """测试根据店铺ID获取书籍返回空列表 (stub实现)"""
        result = await book_repository.get_by_shop_id("any_shop")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_search_by_title_returns_empty_list(self, book_repository):
        """测试根据标题搜索返回空列表 (stub实现)"""
        result = await book_repository.search_by_title("any_title")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_search_by_author_returns_empty_list(self, book_repository):
        """测试根据作者搜索返回空列表 (stub实现)"""
        result = await book_repository.search_by_author("any_author")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_update_book_returns_none(self, book_repository):
        """测试更新书籍返回None (stub实现)"""
        result = await book_repository.update("any_isbn", {"title": "新标题"})
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_stock_returns_none(self, book_repository):
        """测试更新库存返回None (stub实现)"""
        result = await book_repository.update_stock("any_isbn", 10)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_book_returns_false(self, book_repository):
        """测试删除书籍返回False (stub实现)"""
        result = await book_repository.delete("any_isbn")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_low_stock_books_returns_empty_list(self, book_repository):
        """测试获取低库存书籍返回空列表 (stub实现)"""
        result = await book_repository.get_low_stock_books(5)
        assert result == []