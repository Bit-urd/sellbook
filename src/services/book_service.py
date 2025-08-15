"""
书籍业务服务层
"""
from typing import List, Dict, Any, Optional
from src.repositories.book_repository import BookRepository
from src.models.book import Book
from src.exceptions import BookNotFoundError, DuplicateBookError


class BookService:
    """书籍服务类"""
    
    def __init__(self, book_repository: BookRepository):
        self.book_repository = book_repository
    
    async def create_book(self, book_data: Dict[str, Any]) -> Book:
        """创建书籍"""
        # 检查书籍是否已存在
        existing_book = await self.book_repository.get_by_isbn(book_data["isbn"])
        if existing_book:
            raise DuplicateBookError(f"Book with ISBN {book_data['isbn']} already exists")
        
        return await self.book_repository.create(book_data)
    
    async def get_book_by_isbn(self, isbn: str) -> Book:
        """根据ISBN获取书籍"""
        book = await self.book_repository.get_by_isbn(isbn)
        if not book:
            raise BookNotFoundError(f"Book with ISBN {isbn} not found")
        return book
    
    async def get_books_by_shop(self, shop_id: str) -> List[Book]:
        """根据店铺获取书籍"""
        return await self.book_repository.get_by_shop_id(shop_id)
    
    async def search_books_by_title(self, title_keyword: str) -> List[Book]:
        """根据标题搜索书籍"""
        return await self.book_repository.search_by_title(title_keyword)
    
    async def search_books_by_author(self, author_keyword: str) -> List[Book]:
        """根据作者搜索书籍"""
        return await self.book_repository.search_by_author(author_keyword)
    
    async def update_book(self, isbn: str, update_data: Dict[str, Any]) -> Book:
        """更新书籍"""
        book = await self.book_repository.update(isbn, update_data)
        if not book:
            raise BookNotFoundError(f"Book with ISBN {isbn} not found")
        return book
    
    async def update_stock(self, isbn: str, new_quantity: int) -> Book:
        """更新库存"""
        book = await self.book_repository.update_stock(isbn, new_quantity)
        if not book:
            raise BookNotFoundError(f"Book with ISBN {isbn} not found")
        return book
    
    async def delete_book(self, isbn: str) -> bool:
        """删除书籍"""
        success = await self.book_repository.delete(isbn)
        if not success:
            raise BookNotFoundError(f"Book with ISBN {isbn} not found")
        return success
    
    async def get_low_stock_books(self, threshold: int = 5) -> List[Book]:
        """获取低库存书籍"""
        return await self.book_repository.get_low_stock_books(threshold)
    
    async def search_isbn_info(self, isbn: str) -> Optional[Dict[str, Any]]:
        """搜索ISBN信息"""
        from src.crawlers.isbn_crawler import ISBNCrawler
        
        crawler = ISBNCrawler()
        result = await crawler.search_book_info(isbn)
        return result