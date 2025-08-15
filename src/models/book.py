"""
书籍模型
"""
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

@dataclass
class Book:
    """书籍模型"""
    isbn: str
    title: str
    shop_id: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[date] = None
    price: Optional[Decimal] = None
    stock_quantity: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def __repr__(self):
        return f"Book(isbn='{self.isbn}', title='{self.title}')"