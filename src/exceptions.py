"""
业务异常定义
"""

class SellBookException(Exception):
    """基础异常类"""
    pass

class ShopNotFoundError(SellBookException):
    """店铺未找到异常"""
    pass

class DuplicateShopError(SellBookException):
    """重复店铺异常"""
    pass

class BookNotFoundError(SellBookException):
    """书籍未找到异常"""
    pass

class DuplicateBookError(SellBookException):
    """重复书籍异常"""
    pass