#!/usr/bin/env python3
"""
SQLite数据库管理模块
负责数据模型定义、连接管理和数据操作
"""
import sqlite3
import asyncio
import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import csv
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器 - 统一管理SQLite数据库操作"""
    
    def __init__(self, db_path: str = "sellbook.db"):
        self.db_path = db_path
        self.db_file = Path(db_path)
        
    async def init_database(self):
        """初始化数据库，创建所有表"""
        async with aiosqlite.connect(self.db_path) as db:
            await self.create_tables(db)
            logger.info(f"数据库初始化完成: {self.db_path}")
    
    async def create_tables(self, db: aiosqlite.Connection):
        """创建数据库表结构"""
        
        # 1. 书籍基础信息表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS books (
                itemid TEXT PRIMARY KEY,
                shopid TEXT NOT NULL,
                isbn TEXT,
                title TEXT,
                author TEXT,
                publisher TEXT,
                publish_year TEXT,
                quality TEXT,
                price REAL,
                display_price TEXT,
                book_url TEXT,
                catnum TEXT,
                userid TEXT,
                scraped_time TEXT,
                scraped_shop_id TEXT,
                scraped_page INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 销售记录详情表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sales_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_isbn TEXT NOT NULL,
                book_title TEXT,
                sale_date TEXT,
                sold_time TEXT,
                price REAL,
                quality TEXT,
                display_title TEXT,
                book_link TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. API销售数据表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_sales_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_isbn TEXT NOT NULL,
                sale_date TEXT,
                sold_time TEXT,
                price REAL,
                quality TEXT,
                analyzed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. 销售统计汇总表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sales_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                sales_count INTEGER DEFAULT 0,
                total_amount REAL DEFAULT 0,
                avg_price REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
        """)
        
        # 创建索引以提升查询性能
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn)",
            "CREATE INDEX IF NOT EXISTS idx_books_shopid ON books(shopid)",
            "CREATE INDEX IF NOT EXISTS idx_sales_records_isbn ON sales_records(book_isbn)",
            "CREATE INDEX IF NOT EXISTS idx_sales_records_date ON sales_records(sale_date)",
            "CREATE INDEX IF NOT EXISTS idx_api_sales_isbn ON api_sales_data(book_isbn)",
            "CREATE INDEX IF NOT EXISTS idx_api_sales_date ON api_sales_data(sale_date)",
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
        
        await db.commit()
    
    async def migrate_from_csv(self):
        """从CSV文件迁移数据到数据库"""
        await self.init_database()
        
        # 迁移书籍数据
        await self._migrate_books_data()
        
        # 迁移API销售数据  
        await self._migrate_api_sales_data()
        
        # 迁移销售统计数据
        await self._migrate_sales_stats()
        
        logger.info("CSV数据迁移完成")
    
    async def _migrate_books_data(self):
        """迁移books_data.csv"""
        csv_file = "books_data.csv"
        if not Path(csv_file).exists():
            logger.warning(f"CSV文件不存在: {csv_file}")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                books_data = []
                
                for row in reader:
                    books_data.append((
                        row.get('itemid', ''),
                        row.get('shopid', ''),
                        row.get('isbn', ''),
                        row.get('title', ''),
                        row.get('author', ''),
                        row.get('publisher', ''),
                        row.get('publish_year', ''),
                        row.get('quality', ''),
                        float(row.get('price', 0)) if row.get('price') else None,
                        row.get('display_price', ''),
                        row.get('book_url', ''),
                        row.get('catnum', ''),
                        row.get('userid', ''),
                        row.get('scraped_time', ''),
                        row.get('scraped_shop_id', ''),
                        int(row.get('scraped_page', 0)) if row.get('scraped_page') else None,
                    ))
                
                await db.executemany("""
                    INSERT OR REPLACE INTO books 
                    (itemid, shopid, isbn, title, author, publisher, publish_year, 
                     quality, price, display_price, book_url, catnum, userid, 
                     scraped_time, scraped_shop_id, scraped_page)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, books_data)
                
                await db.commit()
                logger.info(f"已迁移 {len(books_data)} 条书籍数据")
    
    async def _migrate_api_sales_data(self):
        """迁移api_sales_data.csv"""
        csv_file = "api_sales_data.csv"
        if not Path(csv_file).exists():
            logger.warning(f"CSV文件不存在: {csv_file}")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                sales_data = []
                
                for row in reader:
                    sales_data.append((
                        row.get('book_isbn', ''),
                        row.get('sale_date', ''),
                        row.get('sold_time', ''),
                        float(row.get('price', 0)) if row.get('price') else None,
                        row.get('quality', ''),
                        row.get('analyzed_at', ''),
                    ))
                
                await db.executemany("""
                    INSERT INTO api_sales_data 
                    (book_isbn, sale_date, sold_time, price, quality, analyzed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, sales_data)
                
                await db.commit()
                logger.info(f"已迁移 {len(sales_data)} 条API销售数据")
    
    async def _migrate_sales_stats(self):
        """迁移book_sales.csv"""
        csv_file = "book_sales.csv"
        if not Path(csv_file).exists():
            logger.warning(f"CSV文件不存在: {csv_file}")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                stats_data = []
                
                for row in reader:
                    stats_data.append((
                        row.get('date', ''),
                        int(row.get('sales_count', 0)) if row.get('sales_count') else 0,
                    ))
                
                await db.executemany("""
                    INSERT OR REPLACE INTO sales_stats (date, sales_count)
                    VALUES (?, ?)
                """, stats_data)
                
                await db.commit()
                logger.info(f"已迁移 {len(stats_data)} 条销售统计数据")

class BookRepository:
    """书籍数据仓库 - 负责书籍相关的数据操作"""
    
    def __init__(self, db_path: str = "sellbook.db"):
        self.db_path = db_path
    
    async def save_books(self, books_data: List[Dict[str, Any]]):
        """批量保存书籍数据"""
        async with aiosqlite.connect(self.db_path) as db:
            data_tuples = []
            for book in books_data:
                data_tuples.append((
                    book.get('itemid', ''),
                    book.get('shopid', ''),
                    book.get('isbn', ''),
                    book.get('title', ''),
                    book.get('author', ''),
                    book.get('publisher', ''),
                    book.get('publish_year', ''),
                    book.get('quality', ''),
                    float(book.get('price', 0)) if book.get('price') else None,
                    book.get('display_price', ''),
                    book.get('book_url', ''),
                    book.get('catnum', ''),
                    book.get('userid', ''),
                    book.get('scraped_time', ''),
                    book.get('scraped_shop_id', ''),
                    int(book.get('scraped_page', 0)) if book.get('scraped_page') else None,
                ))
            
            await db.executemany("""
                INSERT OR REPLACE INTO books 
                (itemid, shopid, isbn, title, author, publisher, publish_year, 
                 quality, price, display_price, book_url, catnum, userid, 
                 scraped_time, scraped_shop_id, scraped_page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data_tuples)
            
            await db.commit()
            return len(data_tuples)
    
    async def get_existing_itemids(self) -> set:
        """获取已存在的itemid集合，用于去重"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT itemid FROM books")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
    
    async def get_books_by_isbn(self, isbn: str) -> List[Dict]:
        """根据ISBN获取书籍信息"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM books WHERE isbn = ? ORDER BY created_at DESC",
                (isbn,)
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

class SalesRepository:
    """销售数据仓库 - 负责销售记录相关的数据操作"""
    
    def __init__(self, db_path: str = "sellbook.db"):
        self.db_path = db_path
    
    async def save_sales_data(self, sales_data: List[Dict[str, Any]]):
        """批量保存API销售数据"""
        async with aiosqlite.connect(self.db_path) as db:
            data_tuples = []
            for sale in sales_data:
                data_tuples.append((
                    sale.get('book_isbn', ''),
                    sale.get('sale_date', ''),
                    sale.get('sold_time', ''),
                    float(sale.get('price', 0)) if sale.get('price') else None,
                    sale.get('quality', ''),
                    sale.get('analyzed_at', datetime.now().isoformat()),
                ))
            
            await db.executemany("""
                INSERT INTO api_sales_data 
                (book_isbn, sale_date, sold_time, price, quality, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, data_tuples)
            
            await db.commit()
            return len(data_tuples)
    
    async def get_sales_by_isbn(self, isbn: str, days_limit: int = 30) -> List[Dict]:
        """根据ISBN获取销售记录"""
        cutoff_date = datetime.now().strftime('%Y-%m-%d')
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT * FROM api_sales_data 
                WHERE book_isbn = ? 
                  AND date(sale_date) >= date('now', '-{} days')
                ORDER BY sale_date DESC
            """.format(days_limit), (isbn,))
            
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

# 数据库初始化脚本
async def init_database_schema():
    """初始化数据库架构"""
    db_manager = DatabaseManager()
    await db_manager.init_database()

if __name__ == "__main__":
    # 测试数据库功能
    async def test_database():
        db_manager = DatabaseManager()
        await db_manager.init_database()
        print("数据库初始化完成")
        
        # 测试迁移
        await db_manager.migrate_from_csv()
        print("CSV迁移完成")
    
    asyncio.run(test_database())