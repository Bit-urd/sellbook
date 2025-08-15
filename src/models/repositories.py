#!/usr/bin/env python3
"""
数据仓库层 - 负责数据的CRUD操作
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json
import logging

from .database import db
from .models import Shop, Book, BookInventory, SalesRecord, CrawlTask, DataStatistics

logger = logging.getLogger(__name__)

class ShopRepository:
    """店铺数据仓库"""
    
    def create(self, shop: Shop) -> int:
        """创建店铺"""
        query = """
            INSERT INTO shops (shop_id, shop_name, platform, shop_url, shop_type, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (shop.shop_id, shop.shop_name, shop.platform, 
                 shop.shop_url, shop.shop_type, shop.status)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    def get_by_id(self, shop_id: str) -> Optional[Dict]:
        """根据shop_id获取店铺"""
        query = "SELECT * FROM shops WHERE shop_id = ?"
        results = db.execute_query(query, (shop_id,))
        return results[0] if results else None
    
    def get_all_active(self) -> List[Dict]:
        """获取所有活跃店铺"""
        query = "SELECT * FROM shops WHERE status = 'active'"
        return db.execute_query(query)
    
    def update_status(self, shop_id: str, status: str) -> bool:
        """更新店铺状态"""
        query = "UPDATE shops SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?"
        return db.execute_update(query, (status, shop_id)) > 0
    
    def batch_create(self, shops: List[Shop]) -> int:
        """批量创建店铺"""
        query = """
            INSERT OR IGNORE INTO shops (shop_id, shop_name, platform, shop_url, shop_type, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (s.shop_id, s.shop_name, s.platform, s.shop_url, s.shop_type, s.status)
            for s in shops
        ]
        return db.execute_many(query, params_list)
    
    def get_paginated(self, offset: int, limit: int, search: Optional[str] = None) -> List[Dict]:
        """获取分页的店铺列表（包含统计信息）"""
        where_clause = ""
        params = []
        
        if search:
            where_clause = "WHERE s.shop_id LIKE ? OR s.shop_name LIKE ?"
            params.extend([f"%{search}%", f"%{search}%"])
        
        # 优化查询：使用更简单的聚合，减少复杂度
        query = f"""
            SELECT s.*,
                   COALESCE(bi_count.total_books, 0) as total_books,
                   COALESCE(b_crawled.crawled_books, 0) as crawled_books,
                   COALESCE(bi_count.total_books - b_crawled.crawled_books, 0) as uncrawled_books,
                   CASE 
                       WHEN COALESCE(bi_count.total_books, 0) = 0 THEN 0
                       ELSE ROUND((COALESCE(b_crawled.crawled_books, 0) * 100.0 / bi_count.total_books), 2)
                   END as crawl_progress,
                   COALESCE(sr_count.total_sales, 0) as total_sales,
                   COALESCE(b_last.last_update, sr_last.last_update) as last_update
            FROM shops s
            LEFT JOIN (
                SELECT shop_id, COUNT(DISTINCT isbn) as total_books 
                FROM book_inventory 
                GROUP BY shop_id
            ) bi_count ON s.id = bi_count.shop_id
            LEFT JOIN (
                SELECT bi.shop_id, COUNT(DISTINCT bi.isbn) as crawled_books
                FROM book_inventory bi
                JOIN books b ON bi.isbn = b.isbn 
                WHERE b.last_sales_update IS NOT NULL
                GROUP BY bi.shop_id
            ) b_crawled ON s.id = b_crawled.shop_id
            LEFT JOIN (
                SELECT shop_id, COUNT(DISTINCT item_id) as total_sales
                FROM sales_records 
                GROUP BY shop_id
            ) sr_count ON s.id = sr_count.shop_id
            LEFT JOIN (
                SELECT bi.shop_id, MAX(b.last_sales_update) as last_update
                FROM book_inventory bi
                JOIN books b ON bi.isbn = b.isbn
                WHERE b.last_sales_update IS NOT NULL
                GROUP BY bi.shop_id
            ) b_last ON s.id = b_last.shop_id
            LEFT JOIN (
                SELECT shop_id, MAX(created_at) as last_update
                FROM sales_records
                GROUP BY shop_id
            ) sr_last ON s.id = sr_last.shop_id
            {where_clause}
            ORDER BY s.created_at DESC 
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        return db.execute_query(query, tuple(params))
    
    def get_total_count(self) -> int:
        """获取店铺总数"""
        query = "SELECT COUNT(*) as total FROM shops"
        result = db.execute_query(query)
        return result[0]['total'] if result else 0
    
    def get_by_shop_id(self, shop_id: str) -> Optional[Dict]:
        """根据shop_id获取店铺"""
        query = "SELECT * FROM shops WHERE shop_id = ?"
        results = db.execute_query(query, (shop_id,))
        return results[0] if results else None
    
    def update(self, shop_id: str, shop: Shop) -> bool:
        """更新店铺信息"""
        query = """
            UPDATE shops 
            SET shop_name = ?, platform = ?, shop_url = ?, shop_type = ?, 
                status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE shop_id = ?
        """
        params = (shop.shop_name, shop.platform, shop.shop_url, 
                 shop.shop_type, shop.status, shop_id)
        return db.execute_update(query, params) > 0
    
    def delete(self, shop_id: str) -> bool:
        """删除店铺（级联删除相关数据）"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 删除相关的书籍库存
                cursor.execute("DELETE FROM book_inventory WHERE shop_id = (SELECT id FROM shops WHERE shop_id = ?)", (shop_id,))
                # 删除相关的销售记录
                cursor.execute("DELETE FROM sales_records WHERE shop_id = (SELECT id FROM shops WHERE shop_id = ?)", (shop_id,))
                # 删除店铺
                cursor.execute("DELETE FROM shops WHERE shop_id = ?", (shop_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"删除店铺失败: {e}")
                conn.rollback()
                return False
    
    def get_shop_with_stats(self, shop_id: str) -> Optional[Dict]:
        """获取店铺详情及统计信息"""
        query = """
            SELECT s.*,
                   COUNT(DISTINCT bi.isbn) as total_books_inventory,
                   COUNT(DISTINCT sr.item_id) as total_sales_records,
                   COUNT(DISTINCT b_all.isbn) as total_books_in_shop,
                   COUNT(DISTINCT CASE WHEN b_all.last_sales_update IS NOT NULL THEN b_all.isbn END) as crawled_books,
                   COUNT(DISTINCT CASE WHEN b_all.last_sales_update IS NULL THEN b_all.isbn END) as uncrawled_books,
                   CASE 
                       WHEN COUNT(DISTINCT b_all.isbn) = 0 THEN 0
                       ELSE ROUND((COUNT(DISTINCT CASE WHEN b_all.last_sales_update IS NOT NULL THEN b_all.isbn END) * 100.0 / 
                                 COUNT(DISTINCT b_all.isbn)), 2)
                   END as crawl_progress,
                   MAX(sr.created_at) as last_sales_update
            FROM shops s
            LEFT JOIN book_inventory bi ON s.id = bi.shop_id
            LEFT JOIN sales_records sr ON s.id = sr.shop_id
            LEFT JOIN (
                SELECT DISTINCT bi2.isbn, b.last_sales_update
                FROM book_inventory bi2
                LEFT JOIN books b ON bi2.isbn = b.isbn
                WHERE bi2.shop_id = (SELECT id FROM shops WHERE shop_id = ?)
            ) b_all ON 1=1
            WHERE s.shop_id = ?
            GROUP BY s.id
        """
        results = db.execute_query(query, (shop_id, shop_id))
        return results[0] if results else None

class BookRepository:
    """书籍数据仓库"""
    
    def create_or_update(self, book: Book) -> Optional[str]:
        """创建或更新书籍，返回ISBN"""
        # 先尝试根据ISBN查找
        if book.isbn:
            existing = self.get_by_isbn(book.isbn)
            if existing:
                logger.warning(f"书籍ISBN {book.isbn} 已存在，跳过插入: {book.title}")
                return book.isbn
        
        try:
            query = """
                INSERT OR IGNORE INTO books (isbn, title, author, publisher, publish_date, 
                                 category, subcategory, description, cover_image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (book.isbn, book.title, book.author, book.publisher, 
                     book.publish_date, book.category, book.subcategory,
                     book.description, book.cover_image_url)
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if cursor.rowcount == 0:
                    logger.warning(f"书籍ISBN {book.isbn} 插入被忽略（可能重复）")
                else:
                    logger.info(f"成功插入书籍: ISBN={book.isbn}, 标题={book.title}")
                return book.isbn
        except Exception as e:
            logger.error(f"插入书籍失败: {e}")
            return None
    
    def get_by_isbn(self, isbn: str) -> Optional[Dict]:
        """根据ISBN获取书籍"""
        query = "SELECT * FROM books WHERE isbn = ?"
        results = db.execute_query(query, (isbn,))
        return results[0] if results else None
    
    def search_by_title(self, title: str) -> List[Dict]:
        """根据标题搜索书籍"""
        query = "SELECT * FROM books WHERE title LIKE ?"
        return db.execute_query(query, (f"%{title}%",))
    
    def get_by_category(self, category: str) -> List[Dict]:
        """根据分类获取书籍"""
        query = "SELECT * FROM books WHERE category = ?"
        return db.execute_query(query, (category,))

class BookInventoryRepository:
    """书籍库存价格数据仓库"""
    
    def upsert(self, inventory: BookInventory) -> int:
        """插入或更新库存信息"""
        # 计算价差和利润率
        if inventory.kongfuzi_price and inventory.duozhuayu_second_hand_price:
            inventory.price_diff_second_hand = inventory.duozhuayu_second_hand_price - inventory.kongfuzi_price
            inventory.profit_margin_second_hand = (inventory.price_diff_second_hand / inventory.kongfuzi_price) * 100
            inventory.is_profitable = inventory.price_diff_second_hand > 0
        
        query = """
            INSERT OR REPLACE INTO book_inventory 
            (isbn, shop_id, kongfuzi_price, kongfuzi_original_price, kongfuzi_stock,
             kongfuzi_condition, kongfuzi_condition_desc, kongfuzi_book_url, kongfuzi_item_id,
             duozhuayu_new_price, duozhuayu_second_hand_price, duozhuayu_in_stock, duozhuayu_book_url,
             price_diff_new, price_diff_second_hand, profit_margin_new, profit_margin_second_hand,
             is_profitable, status, crawled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        params = (
            inventory.isbn, inventory.shop_id,
            inventory.kongfuzi_price, inventory.kongfuzi_original_price, inventory.kongfuzi_stock,
            inventory.kongfuzi_condition, inventory.kongfuzi_condition_desc,
            inventory.kongfuzi_book_url, inventory.kongfuzi_item_id,
            inventory.duozhuayu_new_price, inventory.duozhuayu_second_hand_price,
            1 if inventory.duozhuayu_in_stock else 0, inventory.duozhuayu_book_url,
            inventory.price_diff_new, inventory.price_diff_second_hand,
            inventory.profit_margin_new, inventory.profit_margin_second_hand,
            1 if inventory.is_profitable else 0, inventory.status
        )
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    def get_by_book_shop(self, isbn: str, shop_id: int) -> Optional[Dict]:
        """根据书籍ISBN和店铺ID获取库存"""
        query = "SELECT * FROM book_inventory WHERE isbn = ? AND shop_id = ?"
        results = db.execute_query(query, (isbn, shop_id))
        return results[0] if results else None
    
    def get_profitable_items(self, min_margin: float = 20.0) -> List[Dict]:
        """获取有利润的商品"""
        query = """
            SELECT bi.*, b.title, b.author, s.shop_name
            FROM book_inventory bi
            JOIN books b ON bi.isbn = b.isbn
            JOIN shops s ON bi.shop_id = s.id
            WHERE bi.is_profitable = 1 
              AND bi.profit_margin_second_hand >= ?
            ORDER BY bi.profit_margin_second_hand DESC
        """
        return db.execute_query(query, (min_margin,))

class SalesRepository:
    """销售记录数据仓库"""
    
    def create(self, sale: SalesRecord) -> str:
        """创建销售记录（使用item_id作为主键自动去重）"""
        insert_query = """
            INSERT OR IGNORE INTO sales_records 
            (item_id, isbn, shop_id, sale_price, original_price, sale_date, sale_platform, book_condition)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        insert_params = (sale.item_id, sale.isbn, sale.shop_id, sale.sale_price, sale.original_price,
                        sale.sale_date, sale.sale_platform, sale.book_condition)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_query, insert_params)
            # 返回item_id作为标识符
            return sale.item_id
    
    def batch_create(self, sales: List[SalesRecord]) -> int:
        """批量创建销售记录"""
        query = """
            INSERT OR IGNORE INTO sales_records 
            (item_id, isbn, shop_id, sale_price, original_price, sale_date, sale_platform, book_condition)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (s.item_id, s.isbn, s.shop_id, s.sale_price, s.original_price,
             s.sale_date, s.sale_platform, s.book_condition)
            for s in sales
        ]
        return db.execute_many(query, params_list)
    
    def get_sales_by_period(self, days: int) -> List[Dict]:
        """获取指定天数内的销售记录"""
        query = """
            SELECT sr.*, b.title, b.author, s.shop_name
            FROM sales_records sr
            JOIN books b ON sr.isbn = b.isbn
            JOIN shops s ON sr.shop_id = s.id
            WHERE sr.sale_date >= datetime('now', '-{} days')
            ORDER BY sr.sale_date DESC
        """.format(days)
        return db.execute_query(query)
    
    def get_hot_sales(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """获取热销书籍"""
        query = """
            SELECT b.title, b.isbn, b.author, 
                   COUNT(*) as sale_count,
                   AVG(sr.sale_price) as avg_price,
                   MIN(sr.sale_price) as min_price,
                   MAX(sr.sale_price) as max_price,
                   COALESCE(bi.duozhuayu_second_hand_price, bi.duozhuayu_new_price) as cost_price
            FROM sales_records sr
            JOIN books b ON sr.isbn = b.isbn
            LEFT JOIN book_inventory bi ON sr.isbn = bi.isbn
            WHERE sr.sale_date >= datetime('now', '-{} days')
            GROUP BY sr.isbn
            ORDER BY sale_count DESC
            LIMIT ?
        """.format(days)
        return db.execute_query(query, (limit,))
    
    def get_hot_sales_by_isbn(self, isbn: str) -> List[Dict]:
        """获取指定ISBN的销售统计"""
        query = """
            SELECT b.title, b.isbn, b.author, 
                   COUNT(*) as sale_count,
                   AVG(sr.sale_price) as avg_price,
                   MIN(sr.sale_price) as min_price,
                   MAX(sr.sale_price) as max_price,
                   COALESCE(bi.duozhuayu_second_hand_price, bi.duozhuayu_new_price) as cost_price
            FROM sales_records sr
            JOIN books b ON sr.isbn = b.isbn
            LEFT JOIN book_inventory bi ON sr.isbn = bi.isbn
            WHERE sr.isbn = ?
            GROUP BY sr.isbn
        """
        return db.execute_query(query, (isbn,))
    
    def get_price_statistics(self, isbn: str, days: int = 30) -> Dict:
        """获取价格统计信息"""
        query = """
            SELECT 
                AVG(sale_price) as avg_price,
                MIN(sale_price) as min_price,
                MAX(sale_price) as max_price,
                COUNT(*) as sale_count
            FROM sales_records
            WHERE isbn = ? 
              AND sale_date >= datetime('now', '-{} days')
        """.format(days)
        
        results = db.execute_query(query, (isbn,))
        if results:
            return results[0]
        return {'avg_price': 0, 'min_price': 0, 'max_price': 0, 'sale_count': 0}

class CrawlTaskRepository:
    """爬虫任务数据仓库"""
    
    def create(self, task: CrawlTask) -> int:
        """创建爬虫任务"""
        query = """
            INSERT INTO crawl_tasks 
            (task_name, task_type, target_platform, target_url, shop_id, 
             target_isbn, book_title, task_params, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (task.task_name, task.task_type, task.target_platform,
                 task.target_url, task.shop_id, task.target_isbn, task.book_title,
                 json.dumps(task.task_params) if task.task_params else None,
                 task.priority, task.status)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    def update_status(self, task_id: int, status: str, 
                     progress: float = None, error_message: str = None) -> bool:
        """更新任务状态"""
        updates = ["status = ?"]
        params = [status]
        
        if progress is not None:
            updates.append("progress_percentage = ?")
            params.append(progress)
        
        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)
        
        if status == 'running':
            updates.append("start_time = CURRENT_TIMESTAMP")
        elif status in ['completed', 'failed']:
            updates.append("end_time = CURRENT_TIMESTAMP")
        
        query = f"UPDATE crawl_tasks SET {', '.join(updates)} WHERE id = ?"
        params.append(task_id)
        
        return db.execute_update(query, tuple(params)) > 0
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取待执行的任务"""
        query = """
            SELECT * FROM crawl_tasks 
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
        """
        return db.execute_query(query)
    
    def get_running_tasks(self) -> List[Dict]:
        """获取正在运行的任务"""
        query = "SELECT * FROM crawl_tasks WHERE status = 'running'"
        return db.execute_query(query)
    
    def get_recent_tasks(self, limit: int = 20) -> List[Dict]:
        """获取最近的任务"""
        query = """
            SELECT * FROM crawl_tasks 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        return db.execute_query(query, (limit,))

    def batch_delete(self, task_ids: List[int]) -> int:
        """批量删除任务"""
        if not task_ids:
            return 0
        
        placeholders = ','.join('?' for _ in task_ids)
        query = f"DELETE FROM crawl_tasks WHERE id IN ({placeholders})"
        
        return db.execute_update(query, tuple(task_ids))
    
    def create_book_sales_tasks(self, shop_id: int, book_list: List[Dict]) -> int:
        """为店铺的书籍列表批量创建销售记录爬取任务"""
        created_count = 0
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            for book in book_list:
                # 检查是否已经有该ISBN的爬取任务（pending或running状态）
                check_query = """
                    SELECT COUNT(*) FROM crawl_tasks 
                    WHERE target_isbn = ? AND task_type = 'book_sales_crawl' 
                    AND status IN ('pending', 'running')
                """
                cursor.execute(check_query, (book['isbn'],))
                existing_tasks = cursor.fetchone()[0]
                
                if existing_tasks > 0:
                    continue  # 跳过已有任务的书籍
                
                # 创建任务
                task = CrawlTask(
                    task_name=f"爬取《{book.get('title', 'Unknown')}》销售记录",
                    task_type="book_sales_crawl",
                    target_platform="kongfuzi",
                    shop_id=shop_id,
                    target_isbn=book['isbn'],
                    book_title=book.get('title', 'Unknown'),
                    priority=5,
                    status='pending'
                )
                
                insert_query = """
                    INSERT INTO crawl_tasks 
                    (task_name, task_type, target_platform, shop_id, target_isbn, 
                     book_title, priority, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(insert_query, (
                    task.task_name, task.task_type, task.target_platform,
                    task.shop_id, task.target_isbn, task.book_title,
                    task.priority, task.status
                ))
                created_count += 1
        
        return created_count
    
    def get_book_sales_tasks_by_shop(self, shop_id: int, status: str = None) -> List[Dict]:
        """获取指定店铺的书籍销售爬取任务"""
        if status:
            query = """
                SELECT * FROM crawl_tasks 
                WHERE shop_id = ? AND task_type = 'book_sales_crawl' AND status = ?
                ORDER BY created_at DESC
            """
            return db.execute_query(query, (shop_id, status))
        else:
            query = """
                SELECT * FROM crawl_tasks 
                WHERE shop_id = ? AND task_type = 'book_sales_crawl'
                ORDER BY created_at DESC
            """
            return db.execute_query(query, (shop_id,))
    
    def get_next_pending_book_task(self) -> Optional[Dict]:
        """获取下一个待执行的书籍销售爬取任务"""
        query = """
            SELECT * FROM crawl_tasks 
            WHERE task_type = 'book_sales_crawl' AND status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        """
        results = db.execute_query(query)
        return results[0] if results else None

class StatisticsRepository:
    """统计数据仓库"""
    
    def calculate_and_save_statistics(self, stat_type: str, stat_period: str) -> None:
        """计算并保存统计数据"""
        # 根据统计周期确定时间范围
        days_map = {
            'daily': 1,
            'weekly': 7,
            'monthly': 30
        }
        days = days_map.get(stat_period, 1)
        
        # 计算销售统计
        query = """
            INSERT OR REPLACE INTO data_statistics 
            (stat_type, stat_period, stat_date, total_sales, total_revenue, 
             avg_price, min_price, max_price, calculated_at)
            SELECT 
                ?, ?, date('now'),
                COUNT(*) as total_sales,
                SUM(sale_price) as total_revenue,
                AVG(sale_price) as avg_price,
                MIN(sale_price) as min_price,
                MAX(sale_price) as max_price,
                CURRENT_TIMESTAMP
            FROM sales_records
            WHERE sale_date >= datetime('now', '-{} days')
        """.format(days)
        
        db.execute_update(query, (stat_type, stat_period))
    
    def get_statistics(self, stat_type: str, stat_period: str) -> Optional[Dict]:
        """获取统计数据"""
        query = """
            SELECT * FROM data_statistics 
            WHERE stat_type = ? AND stat_period = ? AND stat_date = date('now')
        """
        results = db.execute_query(query, (stat_type, stat_period))
        return results[0] if results else None