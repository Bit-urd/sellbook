#!/usr/bin/env python3
"""
书籍管理路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import logging

from ..models.repositories import BookRepository, BookInventoryRepository, SalesRepository
from ..models.models import Book
from ..services.crawler_service import KongfuziCrawler
from ..models.database import db

logger = logging.getLogger(__name__)

# 创建路由
book_router = APIRouter(prefix="/api/books", tags=["books"])

# 仓库实例
book_repo = BookRepository()
inventory_repo = BookInventoryRepository()
sales_repo = SalesRepository()

class BookCreateRequest(BaseModel):
    """创建书籍请求"""
    isbn: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None

class BookUpdateRequest(BaseModel):
    """更新书籍请求"""
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_crawled: Optional[int] = None

@book_router.get("")
async def get_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    crawl_status: Optional[str] = Query(None, regex="^(all|crawled|uncrawled)$")
):
    """获取书籍列表（支持搜索、筛选和分页）"""
    try:
        offset = (page - 1) * page_size
        
        # 构建查询
        query = """
            SELECT 
                b.*,
                COUNT(DISTINCT sr.id) as sales_count,
                COUNT(DISTINCT sr.shop_id) as shop_count,
                AVG(sr.sale_price) as avg_price,
                MIN(sr.sale_price) as min_price,
                MAX(sr.sale_price) as max_price
            FROM books b
            LEFT JOIN sales_records sr ON b.isbn = sr.isbn
        """
        
        params = []
        where_clauses = []
        
        # 搜索条件
        if search:
            where_clauses.append("(b.isbn LIKE ? OR b.title LIKE ? OR b.author LIKE ? OR b.publisher LIKE ?)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern] * 4)
        
        # 爬取状态筛选
        if crawl_status == 'crawled':
            where_clauses.append("b.is_crawled = 1")
        elif crawl_status == 'uncrawled':
            where_clauses.append("b.is_crawled = 0")
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " GROUP BY b.id ORDER BY b.updated_at DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        books = db.execute_query(query, tuple(params))
        
        # 获取总数
        count_query = "SELECT COUNT(*) as total FROM books"
        count_params = []
        
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)
            if search:
                count_params.extend([search_pattern] * 4)
            
        total = db.execute_query(count_query, tuple(count_params))[0]['total']
        
        return {
            "success": True,
            "data": {
                "books": books,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
        }
    except Exception as e:
        logger.error(f"获取书籍列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.get("/search")
async def search_books(
    title: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """搜索书籍（支持标题、作者、出版社、分类搜索）"""
    try:
        # 构建搜索条件
        where_clauses = []
        params = []
        
        if title:
            where_clauses.append("title LIKE ?")
            params.append(f"%{title}%")
        
        if author:
            where_clauses.append("author LIKE ?")
            params.append(f"%{author}%")
        
        if publisher:
            where_clauses.append("publisher LIKE ?")
            params.append(f"%{publisher}%")
        
        if category:
            where_clauses.append("category LIKE ?")
            params.append(f"%{category}%")
        
        if not where_clauses:
            # 如果没有搜索条件，返回空结果
            return []
        
        # 分页参数
        offset = (page - 1) * page_size
        
        # 构建查询
        query = "SELECT * FROM books"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        books = db.execute_query(query, tuple(params))
        
        # 根据测试期望，直接返回书籍列表
        return books
        
    except Exception as e:
        logger.error(f"搜索书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.get("/low-stock")
async def get_low_stock_books(threshold: int = Query(10, ge=0)):
    """获取低库存书籍"""
    try:
        # 查询库存低于阈值的书籍
        query = """
            SELECT 
                b.*,
                SUM(bi.kongfuzi_stock) as stock_quantity,
                COUNT(DISTINCT bi.shop_id) as shop_count
            FROM books b
            LEFT JOIN book_inventory bi ON b.isbn = bi.isbn
            WHERE bi.kongfuzi_stock IS NOT NULL
            GROUP BY b.isbn
            HAVING stock_quantity <= ?
            ORDER BY stock_quantity ASC
        """
        
        books = db.execute_query(query, (threshold,))
        
        # 根据测试期望，直接返回书籍列表
        return books
        
    except Exception as e:
        logger.error(f"获取低库存书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.get("/{isbn}")
async def get_book(isbn: str):
    """获取单本书籍详情"""
    try:
        book = book_repo.get_by_isbn(isbn)
        if not book:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        # 获取销售统计
        stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_sales,
                COUNT(DISTINCT shop_id) as shop_count,
                AVG(sale_price) as avg_price,
                MIN(sale_price) as min_price,
                MAX(sale_price) as max_price,
                MAX(sale_date) as last_sale_date
            FROM sales_records
            WHERE isbn = ?
        """, (isbn,))
        
        # 获取价格历史
        price_history = db.execute_query("""
            SELECT 
                DATE(sale_date) as date,
                AVG(sale_price) as avg_price,
                COUNT(*) as sale_count
            FROM sales_records
            WHERE isbn = ?
            GROUP BY DATE(sale_date)
            ORDER BY date DESC
            LIMIT 30
        """, (isbn,))
        
        # 获取在售店铺
        shops = db.execute_query("""
            SELECT DISTINCT
                s.shop_id,
                s.shop_name,
                COUNT(sr.id) as sale_count,
                AVG(sr.sale_price) as avg_price
            FROM shops s
            JOIN sales_records sr ON s.id = sr.shop_id
            WHERE sr.isbn = ?
            GROUP BY s.id
            ORDER BY sale_count DESC
            LIMIT 10
        """, (isbn,))
        
        book['statistics'] = stats[0] if stats else {}
        book['price_history'] = price_history
        book['shops'] = shops
        
        return {"success": True, "data": book}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取书籍详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.post("")
async def create_book(request: BookCreateRequest):
    """创建新书籍"""
    try:
        # 检查ISBN是否已存在
        existing = book_repo.get_by_isbn(request.isbn)
        if existing:
            raise HTTPException(status_code=400, detail="ISBN已存在")
        
        book = Book(
            isbn=request.isbn,
            title=request.title,
            author=request.author,
            publisher=request.publisher,
            publish_date=request.publish_date,
            category=request.category,
            subcategory=request.subcategory,
            description=request.description,
            cover_image_url=request.cover_image_url
        )
        
        isbn = book_repo.create_or_update(book)
        
        return {
            "success": True,
            "message": "书籍创建成功",
            "data": {"isbn": isbn}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.put("/{isbn}")
async def update_book(isbn: str, request: BookUpdateRequest):
    """更新书籍信息"""
    try:
        book = book_repo.get_by_isbn(isbn)
        if not book:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        update_fields = []
        params = []
        
        if request.title is not None:
            update_fields.append("title = ?")
            params.append(request.title)
        
        if request.author is not None:
            update_fields.append("author = ?")
            params.append(request.author)
        
        if request.publisher is not None:
            update_fields.append("publisher = ?")
            params.append(request.publisher)
        
        if request.publish_date is not None:
            update_fields.append("publish_date = ?")
            params.append(request.publish_date)
        
        if request.category is not None:
            update_fields.append("category = ?")
            params.append(request.category)
        
        if request.subcategory is not None:
            update_fields.append("subcategory = ?")
            params.append(request.subcategory)
        
        if request.description is not None:
            update_fields.append("description = ?")
            params.append(request.description)
        
        if request.cover_image_url is not None:
            update_fields.append("cover_image_url = ?")
            params.append(request.cover_image_url)
        
        if request.is_crawled is not None:
            update_fields.append("is_crawled = ?")
            params.append(request.is_crawled)
            if request.is_crawled == 1:
                update_fields.append("last_sales_update = CURRENT_TIMESTAMP")
        
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE books SET {', '.join(update_fields)} WHERE isbn = ?"
            params.append(isbn)
            
            db.execute_update(query, tuple(params))
        
        return {"success": True, "message": "书籍更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.delete("/{isbn}")
async def delete_book(isbn: str):
    """删除书籍"""
    try:
        book = book_repo.get_by_isbn(isbn)
        if not book:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        # 删除相关数据
        db.execute_update("DELETE FROM sales_records WHERE isbn = ?", (isbn,))
        db.execute_update("DELETE FROM book_inventory WHERE isbn = ?", (isbn,))
        db.execute_update("DELETE FROM books WHERE isbn = ?", (isbn,))
        
        return {"success": True, "message": "书籍删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.post("/{isbn}/crawl")
async def crawl_book_sales(isbn: str):
    """爬取单本书籍的销售数据"""
    try:
        book = book_repo.get_by_isbn(isbn)
        if not book:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        crawler = KongfuziCrawler()
        
        # 爬取书籍销售数据
        stats = await crawler.analyze_book_sales(isbn, days_limit=30)
        
        # 更新书籍爬取状态
        db.execute_update("""
            UPDATE books 
            SET is_crawled = 1, 
                last_sales_update = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE isbn = ?
        """, (isbn,))
        
        return {
            "success": True,
            "message": "书籍销售数据爬取成功",
            "data": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"爬取书籍销售数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.post("/batch-crawl")
async def batch_crawl_books(isbn_list: List[str]):
    """批量爬取多本书籍的销售数据"""
    try:
        results = []
        crawler = KongfuziCrawler()
        
        for isbn in isbn_list:
            try:
                book = book_repo.get_by_isbn(isbn)
                if not book:
                    results.append({
                        "isbn": isbn,
                        "success": False,
                        "message": "书籍不存在"
                    })
                    continue
                
                # 爬取销售数据
                stats = await crawler.analyze_book_sales(isbn, days_limit=30)
                
                # 更新爬取状态
                db.execute_update("""
                    UPDATE books 
                    SET is_crawled = 1, 
                        last_sales_update = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE isbn = ?
                """, (isbn,))
                
                results.append({
                    "isbn": isbn,
                    "success": True,
                    "message": f"爬取成功，获取 {stats.get('total_records', 0)} 条记录"
                })
                
            except Exception as e:
                results.append({
                    "isbn": isbn,
                    "success": False,
                    "message": str(e)
                })
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            "success": True,
            "message": f"批量爬取完成：成功 {success_count}/{len(isbn_list)}",
            "data": results
        }
    except Exception as e:
        logger.error(f"批量爬取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@book_router.get("/stats/crawl-summary")
async def get_crawl_summary():
    """获取书籍爬取统计摘要"""
    try:
        summary = db.execute_query("""
            SELECT 
                COUNT(*) as total_books,
                SUM(CASE WHEN is_crawled = 1 THEN 1 ELSE 0 END) as crawled_books,
                SUM(CASE WHEN is_crawled = 0 THEN 1 ELSE 0 END) as uncrawled_books,
                SUM(CASE WHEN last_sales_update > datetime('now', '-1 day') THEN 1 ELSE 0 END) as updated_today,
                SUM(CASE WHEN last_sales_update > datetime('now', '-7 days') THEN 1 ELSE 0 END) as updated_this_week,
                SUM(CASE WHEN last_sales_update > datetime('now', '-30 days') THEN 1 ELSE 0 END) as updated_this_month
            FROM books
        """)[0]
        
        summary['crawl_rate'] = round((summary['crawled_books'] / summary['total_books'] * 100), 2) if summary['total_books'] > 0 else 0
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        logger.error(f"获取爬取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))