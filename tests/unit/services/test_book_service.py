"""
BookService单元测试
"""
import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from src.services.book_service import BookService
from src.repositories.book_repository import BookRepository
from src.models.book import Book
from src.exceptions import BookNotFoundError, DuplicateBookError
from tests.fixtures.sample_data import SAMPLE_BOOKS, SAMPLE_ISBN_SEARCH_RESULTS


class TestBookService:
    """BookService测试类"""
    
    @pytest.fixture
    def mock_book_repository(self):
        """模拟BookRepository"""
        return AsyncMock(spec=BookRepository)
    
    @pytest.fixture
    def book_service(self, mock_book_repository):
        """创建BookService实例"""
        return BookService(mock_book_repository)
    
    @pytest.mark.asyncio
    async def test_create_book_success(self, book_service, mock_book_repository):
        """测试成功创建书籍"""
        book_data = {
            "isbn": "9787111111111",
            "title": "新书籍",
            "author": "作者",
            "publisher": "出版社",
            "price": Decimal("59.00"),
            "stock_quantity": 10,
            "shop_id": "shop1"
        }
        
        # 模拟仓库层返回
        mock_book_repository.get_by_isbn.return_value = None  # 书籍不存在
        mock_book_repository.create.return_value = Book(**book_data)
        
        result = await book_service.create_book(book_data)
        
        # 验证调用
        mock_book_repository.get_by_isbn.assert_called_once_with(book_data["isbn"])
        mock_book_repository.create.assert_called_once_with(book_data)
        
        # 验证返回值
        assert isinstance(result, Book)
        assert result.isbn == book_data["isbn"]
        assert result.title == book_data["title"]
    
    @pytest.mark.asyncio
    async def test_create_book_duplicate_error(self, book_service, mock_book_repository):
        """测试创建重复书籍抛出异常"""
        book_data = SAMPLE_BOOKS[0].copy()
        existing_book = Book(**book_data)
        
        # 模拟书籍已存在
        mock_book_repository.get_by_isbn.return_value = existing_book
        
        with pytest.raises(DuplicateBookError):
            await book_service.create_book(book_data)
        
        # 验证只调用了检查方法，没有调用创建方法
        mock_book_repository.get_by_isbn.assert_called_once()
        mock_book_repository.create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_book_by_isbn_success(self, book_service, mock_book_repository):
        """测试成功获取书籍"""
        isbn = "9787111213826"
        expected_book = Book(**SAMPLE_BOOKS[0])
        
        mock_book_repository.get_by_isbn.return_value = expected_book
        
        result = await book_service.get_book_by_isbn(isbn)
        
        # 验证调用
        mock_book_repository.get_by_isbn.assert_called_once_with(isbn)
        
        # 验证返回值
        assert result == expected_book
    
    @pytest.mark.asyncio
    async def test_get_book_by_isbn_not_found(self, book_service, mock_book_repository):
        """测试获取不存在的书籍抛出异常"""
        isbn = "9999999999999"
        
        mock_book_repository.get_by_isbn.return_value = None
        
        with pytest.raises(BookNotFoundError):
            await book_service.get_book_by_isbn(isbn)
    
    @pytest.mark.asyncio
    async def test_get_books_by_shop(self, book_service, mock_book_repository):
        """测试根据店铺获取书籍"""
        shop_id = "shop1"
        expected_books = [Book(**book_data) for book_data in SAMPLE_BOOKS if book_data["shop_id"] == shop_id]
        
        mock_book_repository.get_by_shop_id.return_value = expected_books
        
        result = await book_service.get_books_by_shop(shop_id)
        
        # 验证调用
        mock_book_repository.get_by_shop_id.assert_called_once_with(shop_id)
        
        # 验证返回值
        assert result == expected_books
    
    @pytest.mark.asyncio
    async def test_search_books_by_title(self, book_service, mock_book_repository):
        """测试根据标题搜索书籍"""
        title_keyword = "计算机"
        expected_books = [Book(**book_data) for book_data in SAMPLE_BOOKS if title_keyword in book_data["title"]]
        
        mock_book_repository.search_by_title.return_value = expected_books
        
        result = await book_service.search_books_by_title(title_keyword)
        
        # 验证调用
        mock_book_repository.search_by_title.assert_called_once_with(title_keyword)
        
        # 验证返回值
        assert result == expected_books
    
    @pytest.mark.asyncio
    async def test_search_books_by_author(self, book_service, mock_book_repository):
        """测试根据作者搜索书籍"""
        author_keyword = "谢希仁"
        expected_books = [Book(**book_data) for book_data in SAMPLE_BOOKS if book_data["author"] == author_keyword]
        
        mock_book_repository.search_by_author.return_value = expected_books
        
        result = await book_service.search_books_by_author(author_keyword)
        
        # 验证调用
        mock_book_repository.search_by_author.assert_called_once_with(author_keyword)
        
        # 验证返回值
        assert result == expected_books
    
    @pytest.mark.asyncio
    async def test_update_book_success(self, book_service, mock_book_repository):
        """测试成功更新书籍"""
        isbn = "9787111213826"
        update_data = {"price": Decimal("69.00"), "stock_quantity": 15}
        updated_book = Book(**{**SAMPLE_BOOKS[0], **update_data})
        
        mock_book_repository.update.return_value = updated_book
        
        result = await book_service.update_book(isbn, update_data)
        
        # 验证调用
        mock_book_repository.update.assert_called_once_with(isbn, update_data)
        
        # 验证返回值
        assert result == updated_book
        assert result.price == update_data["price"]
    
    @pytest.mark.asyncio
    async def test_update_book_not_found(self, book_service, mock_book_repository):
        """测试更新不存在的书籍抛出异常"""
        isbn = "9999999999999"
        update_data = {"price": Decimal("69.00")}
        
        mock_book_repository.update.return_value = None
        
        with pytest.raises(BookNotFoundError):
            await book_service.update_book(isbn, update_data)
    
    @pytest.mark.asyncio
    async def test_update_stock_success(self, book_service, mock_book_repository):
        """测试成功更新库存"""
        isbn = "9787111213826"
        new_quantity = 20
        updated_book = Book(**{**SAMPLE_BOOKS[0], "stock_quantity": new_quantity})
        
        mock_book_repository.update_stock.return_value = updated_book
        
        result = await book_service.update_stock(isbn, new_quantity)
        
        # 验证调用
        mock_book_repository.update_stock.assert_called_once_with(isbn, new_quantity)
        
        # 验证返回值
        assert result == updated_book
        assert result.stock_quantity == new_quantity
    
    @pytest.mark.asyncio
    async def test_delete_book_success(self, book_service, mock_book_repository):
        """测试成功删除书籍"""
        isbn = "9787111213826"
        
        mock_book_repository.delete.return_value = True
        
        result = await book_service.delete_book(isbn)
        
        # 验证调用
        mock_book_repository.delete.assert_called_once_with(isbn)
        
        # 验证返回值
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_book_not_found(self, book_service, mock_book_repository):
        """测试删除不存在的书籍抛出异常"""
        isbn = "9999999999999"
        
        mock_book_repository.delete.return_value = False
        
        with pytest.raises(BookNotFoundError):
            await book_service.delete_book(isbn)
    
    @pytest.mark.asyncio
    async def test_get_low_stock_books(self, book_service, mock_book_repository):
        """测试获取低库存书籍"""
        threshold = 5
        expected_books = [Book(**book_data) for book_data in SAMPLE_BOOKS if book_data["stock_quantity"] <= threshold]
        
        mock_book_repository.get_low_stock_books.return_value = expected_books
        
        result = await book_service.get_low_stock_books(threshold)
        
        # 验证调用
        mock_book_repository.get_low_stock_books.assert_called_once_with(threshold)
        
        # 验证返回值
        assert result == expected_books
    
    @pytest.mark.asyncio
    @patch('src.crawlers.isbn_crawler.ISBNCrawler')
    async def test_search_isbn_info_success(self, mock_crawler_class, book_service):
        """测试成功搜索ISBN信息"""
        isbn = "9787111213826"
        expected_result = SAMPLE_ISBN_SEARCH_RESULTS[0]
        
        mock_crawler = mock_crawler_class.return_value
        mock_crawler.search_book_info = AsyncMock(return_value=expected_result)
        
        result = await book_service.search_isbn_info(isbn)
        
        # 验证调用
        mock_crawler.search_book_info.assert_called_once_with(isbn)
        
        # 验证返回值
        assert result == expected_result
    
    @pytest.mark.asyncio
    @patch('src.crawlers.isbn_crawler.ISBNCrawler')
    async def test_search_isbn_info_not_found(self, mock_crawler_class, book_service):
        """测试搜索ISBN信息未找到"""
        isbn = "9999999999999"
        
        mock_crawler = mock_crawler_class.return_value
        mock_crawler.search_book_info = AsyncMock(return_value=None)
        
        result = await book_service.search_isbn_info(isbn)
        
        # 验证返回值
        assert result is None