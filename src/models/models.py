#!/usr/bin/env python3
"""
数据模型定义
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

@dataclass
class Shop:
    """店铺模型"""
    shop_id: str
    shop_name: str
    platform: str = 'kongfuzi'
    shop_url: Optional[str] = None
    shop_type: Optional[str] = None
    status: str = 'active'
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Book:
    """书籍模型"""
    isbn: str  # 唯一业务标识
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    id: Optional[int] = None  # 数据库自增主键
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class BookInventory:
    """书籍库存价格模型"""
    isbn: str   # 书籍ISBN (业务外键)
    shop_id: int
    
    # 孔夫子数据
    kongfuzi_price: Optional[float] = None
    kongfuzi_original_price: Optional[float] = None
    kongfuzi_stock: int = 0
    kongfuzi_condition: Optional[str] = None
    kongfuzi_condition_desc: Optional[str] = None
    kongfuzi_book_url: Optional[str] = None
    kongfuzi_item_id: Optional[str] = None
    
    # 多抓鱼数据
    duozhuayu_new_price: Optional[float] = None
    duozhuayu_second_hand_price: Optional[float] = None
    duozhuayu_in_stock: bool = False
    duozhuayu_book_url: Optional[str] = None
    
    # 价差分析
    price_diff_new: Optional[float] = None
    price_diff_second_hand: Optional[float] = None
    profit_margin_new: Optional[float] = None
    profit_margin_second_hand: Optional[float] = None
    is_profitable: bool = False
    
    status: str = 'active'
    id: Optional[int] = None
    crawled_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class SalesRecord:
    """销售记录模型"""
    item_id: str  # 商品ID，作为主键
    isbn: str     # 书籍ISBN (业务外键)
    shop_id: int
    sale_price: float
    sale_date: datetime
    original_price: Optional[float] = None
    sale_platform: str = 'kongfuzi'
    book_condition: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

@dataclass
class CrawlTask:
    """爬虫任务模型"""
    task_name: str
    task_type: str
    target_platform: str
    target_url: Optional[str] = None
    shop_id: Optional[int] = None
    task_params: Optional[Dict[str, Any]] = None
    priority: int = 5
    status: str = 'pending'
    progress_percentage: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    items_crawled: int = 0
    items_updated: int = 0
    items_failed: int = 0
    error_message: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

@dataclass
class DataStatistics:
    """数据统计模型"""
    stat_type: str
    stat_period: str
    stat_date: str
    
    # 统计维度
    isbn: Optional[str] = None  # 书籍ISBN (业务外键)
    shop_id: Optional[int] = None
    category: Optional[str] = None
    
    # 销售统计
    total_sales: int = 0
    total_revenue: float = 0.0
    avg_price: Optional[float] = None
    median_price: Optional[float] = None
    mode_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    
    # 价差统计
    avg_price_diff: Optional[float] = None
    max_profit_margin: Optional[float] = None
    profitable_items_count: int = 0
    
    id: Optional[int] = None
    calculated_at: Optional[datetime] = None
