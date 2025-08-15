#!/usr/bin/env python3
"""
数据库模型定义和管理
使用SQLite作为持久化存储
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class Database:
    """数据库连接管理器"""
    
    def __init__(self, db_path: str = "data/sellbook.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 店铺表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shop_id TEXT UNIQUE NOT NULL,
                    shop_name TEXT NOT NULL,
                    platform TEXT DEFAULT 'kongfuzi',
                    shop_url TEXT,
                    shop_type TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. 书籍基础信息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT,
                    title TEXT NOT NULL,
                    author TEXT,
                    publisher TEXT,
                    publish_date TEXT,
                    category TEXT,
                    subcategory TEXT,
                    description TEXT,
                    cover_image_url TEXT,
                    last_sales_update TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 3. 书籍价格库存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT REFERENCES books(isbn),
                    shop_id INTEGER REFERENCES shops(id),
                    
                    -- 孔夫子数据
                    kongfuzi_price REAL,
                    kongfuzi_original_price REAL,
                    kongfuzi_stock INTEGER DEFAULT 0,
                    kongfuzi_condition TEXT,
                    kongfuzi_condition_desc TEXT,
                    kongfuzi_book_url TEXT,
                    kongfuzi_item_id TEXT,
                    
                    -- 多抓鱼数据
                    duozhuayu_new_price REAL,
                    duozhuayu_second_hand_price REAL,
                    duozhuayu_in_stock INTEGER DEFAULT 0,
                    duozhuayu_book_url TEXT,
                    
                    -- 价差分析字段
                    price_diff_new REAL,
                    price_diff_second_hand REAL,
                    profit_margin_new REAL,
                    profit_margin_second_hand REAL,
                    is_profitable INTEGER DEFAULT 0,
                    
                    status TEXT DEFAULT 'active',
                    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(isbn, shop_id)
                )
            """)
            
            # 4. 销售记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT REFERENCES books(isbn),
                    shop_id INTEGER REFERENCES shops(id),
                    
                    sale_price REAL NOT NULL,
                    original_price REAL,
                    sale_date TIMESTAMP NOT NULL,
                    sale_platform TEXT DEFAULT 'kongfuzi',
                    book_condition TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 5. 爬虫任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawl_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    target_platform TEXT NOT NULL,
                    target_url TEXT,
                    
                    shop_id INTEGER REFERENCES shops(id),
                    target_isbn TEXT,  -- 目标ISBN（用于书籍级别任务）
                    book_title TEXT,   -- 书籍标题（便于显示）
                    
                    -- 任务参数
                    task_params TEXT,
                    priority INTEGER DEFAULT 5,
                    
                    -- 执行状态
                    status TEXT DEFAULT 'pending',
                    progress_percentage REAL DEFAULT 0,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    
                    -- 执行结果
                    items_crawled INTEGER DEFAULT 0,
                    items_updated INTEGER DEFAULT 0,
                    items_failed INTEGER DEFAULT 0,
                    
                    -- 错误信息
                    error_message TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 添加新字段（兼容已有数据库）
            try:
                cursor.execute("ALTER TABLE crawl_tasks ADD COLUMN target_isbn TEXT")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            
            try:
                cursor.execute("ALTER TABLE crawl_tasks ADD COLUMN book_title TEXT")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            
            # 6. 数据统计缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_type TEXT NOT NULL,
                    stat_period TEXT NOT NULL,
                    stat_date DATE NOT NULL,
                    
                    -- 统计维度
                    isbn TEXT REFERENCES books(isbn),
                    shop_id INTEGER REFERENCES shops(id),
                    category TEXT,
                    
                    -- 销售统计
                    total_sales INTEGER DEFAULT 0,
                    total_revenue REAL DEFAULT 0,
                    avg_price REAL,
                    median_price REAL,
                    mode_price REAL,
                    min_price REAL,
                    max_price REAL,
                    
                    -- 价差统计
                    avg_price_diff REAL,
                    max_profit_margin REAL,
                    profitable_items_count INTEGER DEFAULT 0,
                    
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(stat_type, stat_period, stat_date, isbn, shop_id)
                )
            """)
            
            # 创建索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn)",
                "CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)",
                "CREATE INDEX IF NOT EXISTS idx_inventory_isbn_shop ON book_inventory(isbn, shop_id)",
                "CREATE INDEX IF NOT EXISTS idx_sales_isbn ON sales_records(isbn)",
                "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_records(sale_date)",
                "CREATE INDEX IF NOT EXISTS idx_crawl_status ON crawl_tasks(status)",
                "CREATE INDEX IF NOT EXISTS idx_stats_type_period ON data_statistics(stat_type, stat_period)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            logger.info(f"数据库初始化完成: {self.db_path}")

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """执行查询并返回结果"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """执行更新操作并返回影响的行数"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """批量执行操作"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount

# 单例模式的数据库实例
db = Database()