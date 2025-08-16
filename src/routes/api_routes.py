#!/usr/bin/env python3
"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from datetime import datetime
import logging
import json

from ..services.analysis_service import AnalysisService
from ..services.crawler_service import CrawlerManager, KongfuziCrawler, DuozhuayuCrawler, CrawlerTaskExecutor, crawler_service_v2
from ..services.simple_task_queue import simple_task_queue
# from ..services.window_pool import chrome_pool  # 已合并到autonomous_session_manager
from ..services.autonomous_session_manager import autonomous_session_manager
# 为了兼容性，使用autonomous_session_manager作为chrome_pool
chrome_pool = autonomous_session_manager
from ..models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository,
    SalesRepository, CrawlTaskRepository
)
from ..models.models import Shop, CrawlTask
from ..models.database import db

logger = logging.getLogger(__name__)

# 创建路由
api_router = APIRouter(prefix="/api", tags=["api"])

# 服务实例
analysis_service = AnalysisService()
crawler_manager = CrawlerManager()
shop_repo = ShopRepository()
book_repo = BookRepository()
inventory_repo = BookInventoryRepository()
sales_repo = SalesRepository()
task_repo = CrawlTaskRepository()

@api_router.get("/books")
async def get_books_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索ISBN、书名、作者或出版社"),
    crawl_status: Optional[str] = Query(None, description="爬取状态过滤"),
    sort_by: str = Query("sales_count", regex="^(sales_count|avg_price|cost_price)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$")
):
    """获取书籍列表（分页）"""
    try:
        offset = (page - 1) * page_size
        
        # 构建查询条件
        conditions = []
        params = []
        
        if search:
            search_term = f"%{search}%"
            conditions.append("(isbn LIKE ? OR title LIKE ? OR author LIKE ? OR publisher LIKE ?)")
            params.extend([search_term, search_term, search_term, search_term])
        
        if crawl_status == "crawled":
            conditions.append("last_sales_update IS NOT NULL")
        elif crawl_status == "uncrawled":
            conditions.append("last_sales_update IS NULL")
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        # 构建排序子句
        allowed_sort_fields = {
            'sales_count': '(SELECT COUNT(*) FROM sales_records sr WHERE sr.isbn = b.isbn)',
            'avg_price': '(SELECT AVG(sale_price) FROM sales_records sr WHERE sr.isbn = b.isbn)',
            'cost_price': '(SELECT AVG(bi.duozhuayu_second_hand_price) FROM book_inventory bi WHERE bi.isbn = b.isbn AND bi.duozhuayu_second_hand_price > 0)'
        }
        
        if sort_by in allowed_sort_fields:
            order_clause = f"ORDER BY {allowed_sort_fields[sort_by]} {sort_order.upper()} NULLS LAST"
        else:
            order_clause = "ORDER BY b.last_sales_update DESC NULLS LAST, b.created_at DESC"

        # 获取书籍列表
        from ..models.database import db
        books_query = f"""
            SELECT 
                b.isbn, b.title, b.author, b.publisher, b.last_sales_update, b.created_at,
                (CASE WHEN b.last_sales_update IS NOT NULL THEN 1 ELSE 0 END) as is_crawled,
                (SELECT COUNT(*) FROM sales_records sr WHERE sr.isbn = b.isbn) as sales_count,
                (SELECT AVG(sale_price) FROM sales_records sr WHERE sr.isbn = b.isbn) as avg_price,
                (SELECT AVG(bi.duozhuayu_second_hand_price) FROM book_inventory bi WHERE bi.isbn = b.isbn AND bi.duozhuayu_second_hand_price > 0) as cost_price
            FROM books b
            {where_clause}
            {order_clause}
            LIMIT ? OFFSET ?
        """
        books = db.execute_query(books_query, params + [page_size, offset])
        
        # 获取总数
        count_query = f"SELECT COUNT(*) FROM books b {where_clause}"
        total_result = db.execute_query(count_query, params)
        total = total_result[0]['COUNT(*)'] if total_result else 0
        
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

@api_router.get("/books/{isbn}")
async def get_book_detail(isbn: str):
    """获取书籍详情"""
    try:
        from ..models.database import db
        
        # 获取书籍基本信息
        book_query = """
            SELECT isbn, title, author, publisher, publish_date, category, 
                   subcategory, description, cover_image_url, last_sales_update, 
                   created_at, updated_at
            FROM books WHERE isbn = ?
        """
        books = db.execute_query(book_query, (isbn,))
        if not books:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        book = books[0]
        
        # 获取销售统计
        stats_query = """
            SELECT 
                COUNT(*) as total_sales,
                COUNT(DISTINCT shop_id) as shop_count,
                AVG(sale_price) as avg_price,
                MIN(sale_price) as min_price,
                MAX(sale_price) as max_price
            FROM sales_records WHERE isbn = ?
        """
        stats_result = db.execute_query(stats_query, (isbn,))
        statistics = stats_result[0] if stats_result else {}
        
        # 获取在售店铺
        shops_query = """
            SELECT s.shop_id, s.shop_name, COUNT(*) as sale_count, AVG(sr.sale_price) as avg_price
            FROM sales_records sr
            JOIN shops s ON sr.shop_id = s.id
            WHERE sr.isbn = ?
            GROUP BY s.shop_id, s.shop_name
            ORDER BY sale_count DESC
        """
        shops = db.execute_query(shops_query, (isbn,))
        
        return {
            "success": True,
            "data": {
                **book,
                "statistics": statistics,
                "shops": shops
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取书籍详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/books")
async def create_book(book_data: dict):
    """创建新书籍"""
    try:
        # 检查ISBN是否已存在
        from ..models.database import db
        existing = db.execute_query("SELECT isbn FROM books WHERE isbn = ?", (book_data["isbn"],))
        if existing:
            raise HTTPException(status_code=400, detail="该ISBN已存在")
        
        # 创建书籍记录
        insert_query = """
            INSERT INTO books (isbn, title, author, publisher, publish_date, 
                             category, subcategory, description, cover_image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_query, (
                book_data["isbn"],
                book_data["title"],
                book_data.get("author"),
                book_data.get("publisher"),
                book_data.get("publish_date"),
                book_data.get("category"),
                book_data.get("subcategory"),
                book_data.get("description"),
                book_data.get("cover_image_url")
            ))
            conn.commit()
        
        return {
            "success": True,
            "message": f"书籍 {book_data['title']} 创建成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/books/{isbn}")
async def update_book(isbn: str, book_data: dict):
    """更新书籍信息"""
    try:
        from ..models.database import db
        
        # 检查书籍是否存在
        existing = db.execute_query("SELECT isbn FROM books WHERE isbn = ?", (isbn,))
        if not existing:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        # 更新书籍记录
        update_query = """
            UPDATE books SET 
                title = ?, author = ?, publisher = ?, publish_date = ?,
                category = ?, subcategory = ?, description = ?, cover_image_url = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE isbn = ?
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(update_query, (
                book_data["title"],
                book_data.get("author"),
                book_data.get("publisher"),
                book_data.get("publish_date"),
                book_data.get("category"),
                book_data.get("subcategory"),
                book_data.get("description"),
                book_data.get("cover_image_url"),
                isbn
            ))
            conn.commit()
        
        return {
            "success": True,
            "message": f"书籍 {book_data['title']} 更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/books/{isbn}")
async def delete_book(isbn: str):
    """删除书籍及相关数据"""
    try:
        from ..models.database import db
        
        # 检查书籍是否存在
        existing = db.execute_query("SELECT isbn FROM books WHERE isbn = ?", (isbn,))
        if not existing:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 删除相关的销售记录
            cursor.execute("DELETE FROM sales_records WHERE isbn = ?", (isbn,))
            
            # 删除相关的库存记录
            cursor.execute("DELETE FROM book_inventory WHERE isbn = ?", (isbn,))
            
            # 删除书籍记录
            cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
            
            conn.commit()
        
        return {
            "success": True,
            "message": f"书籍 {isbn} 及相关数据删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/books/{isbn}/crawl")
async def crawl_book_sales(isbn: str):
    """爬取单本书籍的销售数据"""
    try:
        from ..models.database import db
        
        # 检查书籍是否存在
        existing = db.execute_query("SELECT isbn FROM books WHERE isbn = ?", (isbn,))
        if not existing:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        # 创建爬虫任务
        task = CrawlTask(
            task_name=f"爬取书籍 {isbn} 的销售数据",
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            target_isbn=isbn
        )
        task_id = task_repo.create(task)
        
        return {
            "success": True,
            "message": f"已创建书籍 {isbn} 的销售数据爬取任务",
            "task_id": task_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建爬虫任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/books/{isbn}/sales")
async def get_book_sales_records(
    isbn: str, 
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """获取指定书籍的销售记录"""
    try:
        from ..models.database import db
        
        # 检查书籍是否存在
        existing = db.execute_query("SELECT isbn FROM books WHERE isbn = ?", (isbn,))
        if not existing:
            raise HTTPException(status_code=404, detail="书籍不存在")
        
        # 获取销售记录
        query = """
            SELECT item_id, sale_price, sale_date, book_condition, 
                   sale_platform, original_price
            FROM sales_records 
            WHERE isbn = ? 
            ORDER BY sale_date DESC 
            LIMIT ? OFFSET ?
        """
        
        sales_records = db.execute_query(query, (isbn, limit, offset))
        
        return {
            "success": True,
            "data": sales_records
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取销售记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/books/batch-crawl")
async def batch_crawl_books(isbn_list: List[str]):
    """批量爬取书籍销售数据"""
    try:
        if not isbn_list:
            raise HTTPException(status_code=400, detail="ISBN列表不能为空")
        
        task_ids = []
        for isbn in isbn_list:
            task = CrawlTask(
                task_name=f"爬取书籍 {isbn} 的销售数据",
                task_type="book_sales_crawl",
                target_platform="kongfuzi",
                target_isbn=isbn
            )
            task_id = task_repo.create(task)
            task_ids.append(task_id)
        
        return {
            "success": True,
            "message": f"已创建 {len(task_ids)} 个书籍销售数据爬取任务",
            "task_ids": task_ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量创建爬虫任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/dashboard")
async def get_dashboard_data():
    """获取仪表板数据"""
    try:
        data = analysis_service.get_dashboard_data()
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"获取仪表板数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sales/statistics")
async def get_sales_statistics(days: int = Query(7, ge=1, le=365)):
    """获取销售统计数据"""
    try:
        stats = analysis_service.get_sales_statistics(days)
        return {"success": True, "data": stats, "days": days}
    except Exception as e:
        logger.error(f"获取销售统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sales/hot")
async def get_hot_sales(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("sale_count", regex="^(sale_count|avg_price|min_price|max_price|cost_price)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """获取热销排行榜"""
    try:
        hot_sales = analysis_service.get_hot_sales_ranking(days, limit, offset, sort_by, sort_order)
        return {"success": True, "data": hot_sales, "days": days}
    except Exception as e:
        logger.error(f"获取热销排行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sales/trend")
async def get_sales_trend(days: int = Query(30, ge=1, le=365)):
    """获取销售趋势"""
    try:
        trend = analysis_service.get_sales_trend(days)
        return {"success": True, "data": trend}
    except Exception as e:
        logger.error(f"获取销售趋势失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/profitable/items")
async def get_profitable_items(
    min_margin: float = Query(0.0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("price_diff", regex="^(kongfuzi_price|duozhuayu_price|price_diff|profit_rate)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """获取有利润的商品"""
    try:
        items = analysis_service.get_profitable_items(min_margin, limit, offset, sort_by, sort_order)
        return {"success": True, "data": items, "min_margin": min_margin}
    except Exception as e:
        logger.error(f"获取利润商品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/category/statistics")
async def get_category_statistics():
    """获取分类统计"""
    try:
        stats = analysis_service.get_category_statistics()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"获取分类统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/shop/performance")
async def get_shop_performance():
    """获取店铺业绩"""
    try:
        performance = analysis_service.get_shop_performance()
        return {"success": True, "data": performance}
    except Exception as e:
        logger.error(f"获取店铺业绩失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/book/search")
async def search_books(q: str = Query(..., min_length=1)):
    """搜索书籍"""
    try:
        books = book_repo.search_by_title(q)
        return {"success": True, "data": books, "query": q}
    except Exception as e:
        logger.error(f"搜索书籍失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/book/{isbn}/price-comparison")
async def get_price_comparison(isbn: str):
    """获取价格对比"""
    try:
        comparison = analysis_service.get_price_comparison(isbn)
        if not comparison:
            raise HTTPException(status_code=404, detail="未找到该书籍")
        return {"success": True, "data": comparison}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取价格对比失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/isbn/{isbn}/analysis")
async def get_isbn_analysis(isbn: str, quality: str = Query("九品以上", regex="^(九品以上|全部品相)$")):
    """获取ISBN分析数据（GET方式，用于前端调用）
    
    Args:
        isbn: ISBN号码
        quality: 品相筛选 - "九品以上" 或 "全部品相"
    """
    try:
        # 验证ISBN格式
        isbn = isbn.strip()
        if not isbn or len(isbn) < 10:
            raise HTTPException(status_code=400, detail="请输入有效的ISBN号码")
        
        # 获取销售记录数据进行分析
        hot_sales = sales_repo.get_hot_sales_by_isbn(isbn)
        price_distribution = analysis_service.calculate_price_distribution(isbn)
        sales_trend = analysis_service.get_sales_trend(30)  # 获取30天趋势
        
        return {
            "success": True,
            "data": {
                "hot_sales": hot_sales,
                "price_distribution": price_distribution,
                "sales_trend": sales_trend,
                "quality_filter": quality
            }
        }
    except Exception as e:
        logger.error(f"获取ISBN分析数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/book/analyze")
async def analyze_book_sales(isbn: str, quality: str = Query("high", regex="^(high|all)$")):
    """实时分析单本书的销售数据（ISBN搜索）
    
    Args:
        isbn: ISBN号码
        quality: 品相过滤 - "high" (九品以上) 或 "all" (全部品相)
    """
    try:
        # 验证ISBN格式
        isbn = isbn.strip()
        if not isbn or len(isbn) < 10:
            raise HTTPException(status_code=400, detail="请输入有效的ISBN号码")
        
        # 转换品相参数
        quality_filter = "九品以上" if quality == "high" else "全部品相"
        
        # 只添加任务到队列，不直接执行爬取
        task_id = crawler_service_v2.add_isbn_analysis_task(isbn, priority=8)
        
        # 同时添加销售数据爬取任务（如果需要最新数据）
        sales_task_id = crawler_service_v2.add_book_sales_task(
            isbn=isbn, 
            book_title=f"ISBN分析_{isbn}",
            priority=7
        )
        
        # 构建响应 - 返回任务信息而不是爬取结果
        response = {
            "isbn": isbn,
            "task_ids": [task_id, sales_task_id],
            "status": "queued",
            "quality_filter": quality_filter,
            "message": f"已创建分析任务，任务ID: {task_id}, 销售数据任务ID: {sales_task_id}",
            "success": True,
            "note": "请使用 /api/task/{task_id}/status 查询任务状态，/api/isbn/{isbn}/analysis 获取分析结果"
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析书籍销售数据失败: {e}")
        
        # 根据不同错误类型返回用户友好的错误信息
        error_str = str(e)
        error_type = "UNKNOWN_ERROR"
        error_message = "分析失败"
        
        # 分析错误类型
        if "LOGIN_REQUIRED:" in error_str:
            error_type = "LOGIN_REQUIRED"
            error_message = error_str.split("LOGIN_REQUIRED:")[1].strip()
        elif "RATE_LIMITED:" in error_str:
            error_type = "RATE_LIMITED" 
            error_message = error_str.split("RATE_LIMITED:")[1].strip()
        elif "Cannot connect to host localhost:9222" in error_str:
            error_type = "CRAWLER_SERVICE_UNAVAILABLE"
            error_message = "爬虫服务暂时不可用，请稍后再试"
        elif "Chrome" in error_str or "browser" in error_str.lower():
            error_type = "BROWSER_ERROR"
            error_message = "数据抓取服务暂时不可用"
        elif "timeout" in error_str.lower():
            error_type = "TIMEOUT"
            error_message = "请求超时，请稍后再试"
        elif "network" in error_str.lower() or "connection" in error_str.lower():
            error_type = "NETWORK_ERROR"
            error_message = "网络连接异常，请检查网络后重试"
        else:
            error_message = f"分析失败: {error_str}"
        
        return {
            "isbn": isbn,
            "error_type": error_type,
            "message": error_message,
            "success": False,
            "stats": None  # 明确表示没有统计数据，而不是假的0值
        }

# 爬虫控制API（需要认证保护）
crawler_router = APIRouter(prefix="/crawler", tags=["crawler"])

@crawler_router.post("/shop/add")
async def add_shops(shop_ids: List[str]):
    """批量添加店铺"""
    try:
        shops = []
        for shop_id in shop_ids:
            shop = Shop(
                shop_id=shop_id,
                shop_name=f"店铺_{shop_id}",  # 实际应该从网页获取
                platform="kongfuzi"
            )
            shops.append(shop)
        
        count = shop_repo.batch_create(shops)
        
        # 创建爬虫任务
        for shop in shops:
            task = CrawlTask(
                task_name=f"爬取店铺 {shop.shop_id} 的书籍",
                task_type="shop_books",
                target_platform="kongfuzi",
                target_url=shop.shop_id
            )
            task_repo.create(task)
        
        return {
            "success": True, 
            "message": f"成功添加 {count} 个店铺",
            "shop_ids": shop_ids
        }
    except Exception as e:
        logger.error(f"添加店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@crawler_router.post("/shop/{shop_id}/crawl")
async def crawl_shop_books(shop_id: str, max_pages: int = Query(50, ge=1, le=100)):
    """爬取店铺书籍"""
    try:
        # 检查店铺是否存在
        shop = shop_repo.get_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        # 创建爬虫任务
        task = CrawlTask(
            task_name=f"爬取店铺 {shop_id} 的书籍",
            task_type="shop_books",
            target_platform="kongfuzi",
            target_url=shop_id,
            task_params={"max_pages": max_pages}
        )
        task_id = task_repo.create(task)
        
        # 将任务添加到V2队列系统，而不是直接执行
        v2_task_id = crawler_service_v2.add_shop_books_task(
            shop_url=shop_id, 
            shop_id=1,  # 默认shop_id
            max_pages=max_pages,
            priority=6
        )
        
        return {
            "success": True,
            "message": f"已创建店铺爬取任务，将爬取最多 {max_pages} 页",
            "task_id": task_id,  # V1任务ID（用于兼容）
            "v2_task_id": v2_task_id,  # V2任务ID（实际执行）
            "status": "queued",
            "note": "任务已加入队列，请使用任务状态接口查询进度"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"爬取店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@crawler_router.post("/update/all-shops")
async def update_all_shops():
    """更新所有店铺的书籍数据"""
    try:
        shops = shop_repo.get_all_active()
        task_ids = []
        
        for shop in shops:
            task = CrawlTask(
                task_name=f"更新店铺 {shop['shop_id']} 的书籍",
                task_type="shop_books",
                target_platform="kongfuzi",
                target_url=shop['shop_id']
            )
            task_id = task_repo.create(task)
            task_ids.append(task_id)
        
        return {
            "success": True,
            "message": f"已创建 {len(task_ids)} 个更新任务",
            "task_ids": task_ids
        }
    except Exception as e:
        logger.error(f"创建更新任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@crawler_router.post("/update/duozhuayu-prices")
async def update_duozhuayu_prices():
    """更新多抓鱼价格"""
    try:
        # 获取所有需要更新的库存项
        query = """
            SELECT DISTINCT bi.isbn, bi.shop_id
            FROM book_inventory bi
            JOIN books b ON bi.isbn = b.isbn
            WHERE b.isbn IS NOT NULL
              AND (bi.duozhuayu_second_hand_price IS NULL 
                   OR bi.updated_at < datetime('now', '-1 day'))
            LIMIT 100
        """
        from ..models.database import db
        items = db.execute_query(query)
        
        task_ids = []
        for item in items:
            task = CrawlTask(
                task_name=f"更新书籍 {item['isbn']} 的多抓鱼价格",
                task_type="duozhuayu_price",
                target_platform="duozhuayu",
                task_params={
                    "isbn": item['isbn'],
                    "shop_id": item['shop_id']
                }
            )
            task_id = task_repo.create(task)
            task_ids.append(task_id)
        
        return {
            "success": True,
            "message": f"已创建 {len(task_ids)} 个价格更新任务",
            "task_ids": task_ids
        }
    except Exception as e:
        logger.error(f"创建价格更新任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@crawler_router.get("/tasks/status")
async def get_task_status(status: Optional[str] = None):
    """获取任务状态"""
    try:
        if status == "pending":
            tasks = task_repo.get_pending_tasks()
        elif status == "running":
            tasks = task_repo.get_running_tasks()
        elif status == "completed":
            tasks = task_repo.get_completed_tasks()
        else:
            tasks = task_repo.get_recent_tasks(50)
        
        return {"success": True, "data": tasks}
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@crawler_router.post("/tasks/run-pending")
async def run_pending_tasks():
    """运行待执行的任务"""
    try:
        # 使用V2任务队列系统，而不是直接运行
        # 将待处理任务加载到内存队列中
        added_count = await crawler_service_v2.add_pending_tasks_to_v1_queue()
        return {
            "success": True, 
            "message": f"已将 {added_count} 个待处理任务加载到执行队列",
            "added_tasks": added_count,
            "note": "任务将由autonomous_session_manager自动执行"
        }
    except Exception as e:
        logger.error(f"运行任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel

class DeleteTasksRequest(BaseModel):
    task_ids: List[int]

@crawler_router.post("/tasks/delete")
async def delete_tasks(request: DeleteTasksRequest):
    """删除指定的爬虫任务"""
    try:
        deleted_count = task_repo.batch_delete(request.task_ids)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="没有找到要删除的任务")
        return {"success": True, "message": f"成功删除 {deleted_count} 个任务"}
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 销售数据管理路由
sales_data_router = APIRouter(prefix="/sales-data", tags=["sales-data"])

@sales_data_router.get("/shops")
async def get_shops_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索店铺ID或名称")
):
    """获取店铺列表（分页）"""
    try:
        offset = (page - 1) * page_size
        shops = shop_repo.get_paginated(offset, page_size, search)
        total = shop_repo.get_total_count()
        
        return {
            "success": True,
            "data": {
                "shops": shops,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
        }
    except Exception as e:
        logger.error(f"获取店铺列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.get("/shops/{shop_id}")
async def get_shop_detail(shop_id: str):
    """获取店铺详情及统计信息"""
    try:
        shop = shop_repo.get_shop_with_stats(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        return {
            "success": True,
            "data": shop
        }
    except Exception as e:
        logger.error(f"获取店铺详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.post("/shops")
async def create_shop(shop_data: dict):
    """创建新店铺"""
    try:
        # 检查店铺是否已存在
        existing_shop = shop_repo.get_by_shop_id(shop_data.get("shop_id"))
        if existing_shop:
            raise HTTPException(status_code=400, detail="店铺ID已存在")
        
        shop = Shop(
            shop_id=shop_data["shop_id"],
            shop_name=shop_data["shop_name"],
            platform=shop_data.get("platform", "kongfuzi"),
            shop_url=shop_data.get("shop_url"),
            shop_type=shop_data.get("shop_type"),
            status=shop_data.get("status", "active")
        )
        
        shop_repo.create(shop)
        
        return {
            "success": True,
            "message": f"店铺 {shop.shop_id} 创建成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.put("/shops/{shop_id}")
async def update_shop(shop_id: str, shop_data: dict):
    """更新店铺信息"""
    try:
        # 检查店铺是否存在
        existing_shop = shop_repo.get_by_shop_id(shop_id)
        if not existing_shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        shop = Shop(
            shop_id=shop_id,
            shop_name=shop_data["shop_name"],
            platform=shop_data.get("platform", "kongfuzi"),
            shop_url=shop_data.get("shop_url"),
            shop_type=shop_data.get("shop_type"),
            status=shop_data.get("status", "active")
        )
        
        success = shop_repo.update(shop_id, shop)
        if not success:
            raise HTTPException(status_code=500, detail="更新失败")
        
        return {
            "success": True,
            "message": f"店铺 {shop_id} 更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.delete("/shops/{shop_id}")
async def delete_shop(shop_id: str):
    """删除店铺"""
    try:
        # 检查店铺是否存在
        existing_shop = shop_repo.get_by_shop_id(shop_id)
        if not existing_shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        success = shop_repo.delete(shop_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")
        
        return {
            "success": True,
            "message": f"店铺 {shop_id} 及相关数据删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 爬虫任务执行API
task_executor_router = APIRouter(prefix="/task-executor", tags=["task-executor"])

# 创建任务执行器实例
task_executor = CrawlerTaskExecutor()

@task_executor_router.get("/task-types")
async def get_supported_task_types():
    """获取支持的任务类型及其配置"""
    try:
        return {
            "success": True,
            "data": {
                "task_types": task_executor.TASK_TYPE_MAPPING,
                "description": "支持的爬虫任务类型及其参数要求"
            }
        }
    except Exception as e:
        logger.error(f"获取任务类型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/execute-incomplete")
async def execute_incomplete_tasks():
    """执行所有未完成的爬虫任务"""
    try:
        results = await task_executor.execute_incomplete_tasks()
        
        return {
            "success": True,
            "data": results,
            "message": f"执行完成：成功 {results['completed']} 个，失败 {results['failed']} 个，跳过 {results['skipped']} 个"
        }
    except Exception as e:
        logger.error(f"执行未完成任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/execute-task/{task_id}")
async def execute_single_task(task_id: int):
    """执行指定的单个任务"""
    try:
        # 获取任务信息
        task = task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.get('status') not in ['pending', 'failed']:
            raise HTTPException(status_code=400, detail="任务状态不允许执行")
        
        # 执行任务
        result = await task_executor.execute_task_by_type(task)
        
        # 更新任务状态
        if result.get('status') == 'completed':
            task_repo.update_status(
                task_id, 'completed', 
                progress=100.0,
                error_message=task_executor._format_success_message(task.get('task_type'), result)
            )
        elif result.get('status') == 'skipped':
            task_repo.update_status(
                task_id, 'skipped',
                progress=100.0,
                error_message=result.get('message', '任务已跳过')
            )
        else:
            task_repo.update_status(
                task_id, 'failed',
                error_message=result.get('message', '任务执行失败')
            )
        
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "task_type": task.get('task_type'),
                "status": result.get('status'),
                "result": result
            },
            "message": f"任务 {task_id} 执行完成，状态：{result.get('status')}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行任务 {task_id} 失败: {e}")
        # 更新任务状态为失败
        try:
            task_repo.update_status(task_id, 'failed', error_message=str(e))
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/validate-task")
async def validate_task_params(task_data: dict):
    """验证任务参数是否有效"""
    try:
        task_type = task_data.get('task_type')
        if not task_type:
            raise HTTPException(status_code=400, detail="缺少task_type字段")
        
        # 获取任务类型信息
        mapping = task_executor.get_task_method_info(task_type)
        if not mapping:
            raise HTTPException(status_code=400, detail=f"不支持的任务类型: {task_type}")
        
        # 验证参数
        try:
            params = task_executor.validate_task_params(task_type, task_data)
            return {
                "success": True,
                "data": {
                    "task_type": task_type,
                    "mapping": mapping,
                    "validated_params": params
                },
                "message": "任务参数验证通过"
            }
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验证任务参数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.get("/execution-status")
async def get_execution_status():
    """获取当前任务执行状态"""
    try:
        # 获取待执行任务数量
        pending_tasks = task_repo.get_pending_tasks()
        running_tasks = task_repo.get_running_tasks() if hasattr(task_repo, 'get_running_tasks') else []
        
        # 获取爬虫服务状态
        try:
            rate_limit_status = KongfuziCrawler.get_rate_limit_status()
        except:
            rate_limit_status = {"is_rate_limited": False, "error": "无法获取状态"}
        
        return {
            "success": True,
            "data": {
                "pending_tasks_count": len(pending_tasks),
                "running_tasks_count": len(running_tasks),
                "crawler_rate_limit": rate_limit_status,
                "task_types_supported": list(task_executor.TASK_TYPE_MAPPING.keys())
            }
        }
    except Exception as e:
        logger.error(f"获取执行状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.get("/tasks/list")
async def list_crawler_tasks(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    task_type: str = None
):
    """分页查询爬虫任务列表"""
    try:
        # 获取队列状态
        queue_status = simple_task_queue.get_queue_status()
        queued_task_ids = set(queue_status.get("next_tasks", []) + queue_status.get("queue", []))
        running_task_ids = queue_status.get("running_count", 0)
        
        # 构建查询条件
        conditions = []
        params = []
        
        if status == "queued":
            # 队列中的任务：显示在内存队列中的任务
            if not queued_task_ids:
                # 如果内存队列为空，返回空结果
                return {
                    "success": True,
                    "data": {
                        "tasks": [],
                        "pagination": {
                            "current_page": page,
                            "page_size": page_size,
                            "total_count": 0,
                            "total_pages": 0
                        }
                    }
                }
            else:
                placeholders = ",".join(["?"] * len(queued_task_ids))
                conditions.append(f"id IN ({placeholders})")
                params.extend(list(queued_task_ids))
        elif status:
            conditions.append("status = ?")
            params.append(status)
        
        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)
        
        # 构建查询SQL
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 查询总数
        count_sql = f"SELECT COUNT(*) FROM crawl_tasks {where_clause}"
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()[0]
            
            # 查询数据
            data_sql = f"""
                SELECT id, task_name, task_type, status, progress_percentage, 
                       created_at, start_time, task_params
                FROM crawl_tasks {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_sql, params + [page_size, offset])
            rows = cursor.fetchall()
            
            tasks = []
            for row in rows:
                # 解析task_params JSON或从其他字段构造参数
                params_dict = json.loads(row[7]) if row[7] else {}
                
                # 如果task_params为空，从数据库其他字段构造参数显示
                if not params_dict:
                    # 获取额外的字段信息
                    cursor.execute("""
                        SELECT target_isbn, shop_id, target_url, book_title 
                        FROM crawl_tasks WHERE id = ?
                    """, (row[0],))
                    extra_row = cursor.fetchone()
                    
                    if extra_row:
                        target_isbn, shop_id, target_url, book_title = extra_row
                        task_type_val = row[2]
                        
                        if task_type_val == 'book_sales_crawl':
                            params_dict = {
                                'target_isbn': target_isbn,
                                'shop_id': shop_id,
                                'book_title': book_title
                            }
                        elif task_type_val == 'shop_books_crawl':
                            params_dict = {
                                'target_url': target_url,
                                'shop_id': shop_id
                            }
                        elif task_type_val == 'duozhuayu_price':
                            params_dict = {
                                'target_isbn': target_isbn,
                                'shop_id': shop_id
                            }
                        elif task_type_val == 'isbn_analysis':
                            params_dict = {
                                'target_isbn': target_isbn
                            }
                
                # 确定任务实际状态
                task_id = row[0]
                actual_status = row[3]
                if task_id in queued_task_ids:
                    actual_status = "queued"
                # SimpleTaskQueue不维护running_tasks集合，通过数据库状态检查
                task_data = task_repo.get_by_id(task_id)
                if task_data and task_data.get('status') == 'running':
                    actual_status = "running"
                
                task = {
                    "id": task_id,
                    "task_name": row[1], 
                    "task_type": row[2],
                    "status": actual_status,
                    "progress_percentage": row[4] if row[4] is not None else 0,
                    "created_at": row[5],
                    "updated_at": row[6],  # This is actually start_time now
                    "params": params_dict
                }
                tasks.append(task)
            
            # 计算分页信息
            total_pages = (total_count + page_size - 1) // page_size
            
            return {
                "success": True,
                "data": {
                    "tasks": tasks,
                    "pagination": {
                        "current_page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": total_pages
                    }
                }
            }
            
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/tasks/delete-batch")
async def delete_batch_tasks(request: dict):
    """批量删除任务"""
    try:
        task_ids = request.get("task_ids", [])
        if not task_ids:
            raise HTTPException(status_code=400, detail="未选择任务")
            
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 批量删除任务
            placeholders = ",".join(["?"] * len(task_ids))
            cursor.execute(f"DELETE FROM crawl_tasks WHERE id IN ({placeholders})", task_ids)
            affected_rows = cursor.rowcount
            
            conn.commit()
            
        return {
            "success": True,
            "message": f"成功删除 {affected_rows} 个任务"
        }
        
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/tasks/execute-batch")
async def execute_batch_tasks(request: dict):
    """批量将选中任务加入执行队列（状态从pending变为queued）"""
    try:
        task_ids = request.get("task_ids", [])
        if not task_ids:
            raise HTTPException(status_code=400, detail="未选择任务")
        
        # 验证任务状态，确保都是pending或failed状态
        with db.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(task_ids))
            
            # 查询符合条件的任务数量
            cursor.execute(f"""
                SELECT COUNT(*) FROM crawl_tasks 
                WHERE id IN ({placeholders}) AND status IN ('pending', 'failed')
            """, task_ids)
            eligible_count = cursor.fetchone()[0]
            
            if eligible_count == 0:
                raise HTTPException(status_code=400, detail="没有可执行的任务（任务需要是pending或failed状态）")
            
            # 重置失败任务的错误信息，pending任务保持不变
            cursor.execute(f"""
                UPDATE crawl_tasks 
                SET error_message = NULL
                WHERE id IN ({placeholders}) AND status = 'failed'
            """, task_ids)
            
            updated_count = cursor.rowcount
            conn.commit()
            
        logger.info(f"已准备 {eligible_count} 个任务供执行")
        
        return {
            "success": True, 
            "message": f"已准备 {eligible_count} 个任务供执行，autonomous_session_manager将自动处理",
            "ready_count": eligible_count,
            "note": "任务保持pending状态，由autonomous_session_manager自动调度"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.get("/task-types/list")
async def get_task_types_list():
    """获取所有任务类型列表"""
    try:        
        task_types = []
        
        for task_type, config in task_executor.TASK_TYPE_MAPPING.items():
            task_types.append({
                "value": task_type,
                "label": config["description"],
                "required_fields": config["required_fields"],
                "optional_fields": config["optional_fields"]
            })
        
        return {"success": True, "data": task_types}
        
    except Exception as e:
        logger.error(f"获取任务类型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.post("/shop/{shop_id}/crawl-sales")
async def crawl_shop_sales(shop_id: str):
    """爬取单个店铺的销售数据"""
    try:
        shop = shop_repo.get_by_shop_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        # 创建销售数据爬取任务
        task = CrawlTask(
            task_name=f"爬取店铺 {shop_id} 的销售数据",
            task_type="shop_sales",
            target_platform="kongfuzi",
            target_url=shop_id,
            shop_id=shop['id']
        )
        task_id = task_repo.create(task)
        
        # 将任务添加到V2队列系统，而不是直接执行
        v2_task_id = crawler_service_v2.add_shop_books_task(
            shop_url=shop_id,
            shop_id=shop['id'],
            max_pages=50,  # 默认页数
            priority=5
        )
        
        return {
            "success": True,
            "message": f"已创建店铺 {shop_id} 的销售数据爬取任务",
            "task_id": task_id,  # V1任务ID（用于兼容）
            "v2_task_id": v2_task_id,  # V2任务ID（实际执行）
            "shop_id": shop_id,
            "status": "queued",
            "note": "任务已加入队列，将异步执行爬取"
        }
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        logger.error(f"爬取店铺销售数据失败: {error_message}")
        
        # 检查是否为频率限制错误
        rate_limit_keywords = [
            "搜索次数已达到上限", "请求错误，请降低访问频次",
            "更换真实账号使用", "访问频率过高"
        ]
        
        is_rate_limit = any(keyword in error_message for keyword in rate_limit_keywords)
        
        if is_rate_limit:
            # 使用 429 状态码表示频率限制
            raise HTTPException(
                status_code=429, 
                detail="访问频率过高，请稍后再试。建议等待一段时间后重新尝试，或降低爬取频率。"
            )
        else:
            raise HTTPException(status_code=500, detail=error_message)

@sales_data_router.post("/crawl-all-shops")
async def crawl_all_shops_sales():
    """一键爬取所有店铺的销售数据"""
    try:
        shops = shop_repo.get_all_active()
        task_ids = []
        
        for shop in shops:
            task = CrawlTask(
                task_name=f"爬取店铺 {shop['shop_id']} 的销售数据",
                task_type="shop_sales",
                target_platform="kongfuzi",
                target_url=shop['shop_id'],
                shop_id=shop['id']
            )
            task_id = task_repo.create(task)
            task_ids.append(task_id)
        
        # 将任务加载到V2队列系统执行
        added_count = await crawler_service_v2.add_pending_tasks_to_v1_queue()
        
        return {
            "success": True,
            "message": f"已创建 {len(task_ids)} 个销售数据爬取任务",
            "task_ids": task_ids,
            "total_shops": len(shops)
        }
    except Exception as e:
        logger.error(f"创建销售数据爬取任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.get("/shop/{shop_id}/sales-stats")
async def get_shop_sales_stats(shop_id: str):
    """获取店铺销售统计"""
    try:
        shop = shop_repo.get_by_shop_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        # 获取店铺销售统计
        from ..models.database import db
        stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_sales,
                COUNT(DISTINCT isbn) as unique_books,
                AVG(sale_price) as avg_price,
                MIN(sale_price) as min_price,
                MAX(sale_price) as max_price,
                SUM(sale_price) as total_revenue,
                MAX(sale_date) as last_sale_date,
                MIN(sale_date) as first_sale_date
            FROM sales_records
            WHERE shop_id = ?
        """, (shop['id'],))
        
        # 获取最近爬取的书籍
        recent_books = db.execute_query("""
            SELECT b.isbn, b.title, b.last_sales_update
            FROM books b
            JOIN sales_records sr ON b.isbn = sr.isbn
            WHERE sr.shop_id = ?
            ORDER BY b.last_sales_update DESC
            LIMIT 10
        """, (shop['id'],))
        
        return {
            "success": True,
            "data": {
                "shop_info": shop,
                "statistics": stats[0] if stats else {},
                "recent_books": recent_books
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取店铺销售统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.get("/crawler/rate-limit-status")
async def get_rate_limit_status():
    """获取当前封控状态"""
    try:
        status = KongfuziCrawler.get_rate_limit_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"获取封控状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/queue/start-all")
async def start_all_tasks():
    """一键启动所有任务（将待执行任务加入队列）"""
    try:
        added_count = simple_task_queue.add_pending_tasks_to_queue()
        
        return {
            "success": True,
            "message": f"已将 {added_count} 个任务加入执行队列",
            "tasks_added": added_count
        }
    except Exception as e:
        logger.error(f"启动所有任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/queue/clear")
async def clear_task_queue():
    """一键清空任务队列（绿色按钮）"""
    try:
        cleared_count = simple_task_queue.clear_queue()
        
        return {
            "success": True,
            "message": f"已清空队列中的 {cleared_count} 个任务",
            "tasks_cleared": cleared_count
        }
    except Exception as e:
        logger.error(f"清空任务队列失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/queue/clear-all")
async def clear_all_tasks():
    """一键清空所有任务（红色按钮）"""
    try:
        result = simple_task_queue.clear_all_tasks()
        
        return {
            "success": True,
            "message": f"已清空队列中的 {result['queue_cleared']} 个任务，删除了 {result['tasks_deleted']} 个待执行任务",
            "queue_cleared": result["queue_cleared"],
            "tasks_deleted": result["tasks_deleted"]
        }
    except Exception as e:
        logger.error(f"清空所有任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@task_executor_router.post("/tasks/retry-failed")
async def retry_failed_tasks():
    """重试所有失败的任务"""
    try:
        retried_count = simple_task_queue.retry_failed_tasks()
        return {
            "success": True,
            "message": f"已成功重试 {retried_count} 个失败的任务",
            "tasks_retried": retried_count
        }
    except Exception as e:
        logger.error(f"重试失败的任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@task_executor_router.get("/queue/status")
async def get_queue_status():
    """获取任务队列状态"""
    try:
        status = simple_task_queue.get_queue_status()
        
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"获取队列状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.get("/books/crawl-status")
async def get_books_crawl_status(
    status: str = Query("all", regex="^(all|crawled|not_crawled)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_search: Optional[str] = Query(None, description="搜索店铺名称或店铺ID")
):
    """获取书店书籍销售记录爬取列表"""
    try:
        from ..models.database import db
        
        # 构建查询条件
        conditions = []
        params = []
        
        # 爬取状态筛选
        if status == "crawled":
            conditions.append("b.last_sales_update IS NOT NULL")
        elif status == "not_crawled":
            conditions.append("b.last_sales_update IS NULL")
        
        # 店铺搜索筛选
        if shop_search:
            search_term = f"%{shop_search}%"
            conditions.append("(s.shop_name LIKE ? OR s.shop_id LIKE ?)")
            params.extend([search_term, search_term])
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        # 获取总数
        total_query = f"""
            SELECT COUNT(DISTINCT bi.isbn) as total 
            FROM book_inventory bi
            JOIN books b ON bi.isbn = b.isbn
            LEFT JOIN shops s ON bi.shop_id = s.id
            {where_clause}
        """
        total_result = db.execute_query(total_query, params)
        total = total_result[0]['total'] if total_result else 0
        
        # 获取分页数据
        offset = (page - 1) * page_size
        books_query = f"""
            SELECT DISTINCT
                b.isbn, b.title, b.author, b.publisher,
                b.last_sales_update, b.created_at, b.updated_at,
                s.shop_name, s.shop_id,
                (CASE WHEN b.last_sales_update IS NOT NULL THEN 1 ELSE 0 END) as is_crawled
            FROM book_inventory bi
            JOIN books b ON bi.isbn = b.isbn
            LEFT JOIN shops s ON bi.shop_id = s.id
            {where_clause}
            ORDER BY b.last_sales_update DESC NULLS LAST, s.shop_name ASC
            LIMIT ? OFFSET ?
        """
        books = db.execute_query(books_query, params + [page_size, offset])
        
        # 统计信息
        stats = db.execute_query("""
            SELECT 
                COUNT(DISTINCT b.isbn) as total_books,
                SUM(CASE WHEN b.last_sales_update IS NOT NULL THEN 1 ELSE 0 END) as crawled_count,
                SUM(CASE WHEN b.last_sales_update IS NULL THEN 1 ELSE 0 END) as not_crawled_count
            FROM book_inventory bi
            JOIN books b ON bi.isbn = b.isbn
            LEFT JOIN shops s ON bi.shop_id = s.id
        """)[0]
        
        return {
            "success": True,
            "data": {
                "books": books,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                },
                "statistics": stats
            }
        }
    except Exception as e:
        logger.error(f"获取书店书籍销售记录爬取列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 新增批量操作API
from pydantic import BaseModel
from typing import List

class BatchShopRequest(BaseModel):
    shop_ids: List[str]  # 店铺ID列表

@sales_data_router.post("/batch-crawl-sales")
async def batch_crawl_shops_sales(request: BatchShopRequest):
    """批量爬取指定店铺的销售数据（书籍级别任务）"""
    try:
        if not request.shop_ids:
            raise HTTPException(status_code=400, detail="店铺ID列表不能为空")
        
        total_tasks_created = 0
        shop_task_summary = []
        
        for shop_id in request.shop_ids:
            # 获取店铺信息
            shop = shop_repo.get_by_shop_id(shop_id)
            if not shop:
                shop_task_summary.append({
                    "shop_id": shop_id,
                    "status": "error",
                    "message": f"店铺 {shop_id} 不存在",
                    "tasks_created": 0
                })
                continue
            
            # 获取店铺的书籍列表
            from ..models.database import db
            books = db.execute_query("""
                SELECT DISTINCT bi.isbn, b.title
                FROM book_inventory bi
                LEFT JOIN books b ON bi.isbn = b.isbn
                WHERE bi.shop_id = ? AND bi.isbn IS NOT NULL
                ORDER BY bi.crawled_at DESC
            """, (shop['id'],))
            
            if not books:
                shop_task_summary.append({
                    "shop_id": shop_id,
                    "status": "warning", 
                    "message": f"店铺 {shop_id} 没有书籍库存记录",
                    "tasks_created": 0
                })
                continue
            
            # 为该店铺的每本书创建销售记录爬取任务
            tasks_created = task_repo.create_book_sales_tasks(shop['id'], books)
            total_tasks_created += tasks_created
            
            shop_task_summary.append({
                "shop_id": shop_id,
                "shop_name": shop.get('shop_name', f"店铺_{shop_id}"),
                "status": "success",
                "message": f"已创建 {tasks_created} 个书籍销售爬取任务",
                "tasks_created": tasks_created,
                "total_books": len(books)
            })
        
        return {
            "success": True,
            "message": f"批量操作完成，总共创建了 {total_tasks_created} 个书籍级别的销售爬取任务",
            "total_tasks_created": total_tasks_created,
            "shop_details": shop_task_summary
        }
        
    except Exception as e:
        logger.error(f"批量创建销售爬取任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sales_data_router.post("/batch-update-books")  
async def batch_update_shops_books(request: BatchShopRequest):
    """批量更新指定店铺的书籍数据"""
    try:
        if not request.shop_ids:
            raise HTTPException(status_code=400, detail="店铺ID列表不能为空")
        
        task_ids = []
        shop_task_summary = []
        
        for shop_id in request.shop_ids:
            # 检查店铺是否存在
            shop = shop_repo.get_by_shop_id(shop_id)
            if not shop:
                shop_task_summary.append({
                    "shop_id": shop_id,
                    "status": "error",
                    "message": f"店铺 {shop_id} 不存在",
                    "task_id": None
                })
                continue
            
            # 创建店铺书籍更新任务
            task = CrawlTask(
                task_name=f"更新店铺 {shop_id} 的书籍数据",
                task_type="shop_books_crawl",
                target_platform="kongfuzi",
                target_url=f"https://shop.kongfz.com/{shop_id}/all/0_50_0_0_1_newItem_desc_0_0/",
                shop_id=shop['id']
            )
            task_id = task_repo.create(task)
            task_ids.append(task_id)
            
            shop_task_summary.append({
                "shop_id": shop_id,
                "shop_name": shop.get('shop_name', f"店铺_{shop_id}"),
                "status": "success",
                "message": f"已创建书籍更新任务",
                "task_id": task_id
            })
        
        return {
            "success": True,
            "message": f"批量操作完成，总共创建了 {len(task_ids)} 个店铺书籍更新任务",
            "total_tasks_created": len(task_ids),
            "task_ids": task_ids,
            "shop_details": shop_task_summary
        }
        
    except Exception as e:
        logger.error(f"批量创建书籍更新任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 窗口池管理API
window_pool_router = APIRouter(prefix="/window-pool", tags=["window-pool"])

@window_pool_router.get("/status")
async def get_window_pool_status():
    """获取窗口池状态"""
    try:
        # 如果窗口池未初始化，返回基本状态信息
        if not autonomous_session_manager._initialized:
            return {
                "success": True,
                "data": {
                    "connected": False,
                    "initialized": False,
                    "pool_size": autonomous_session_manager.max_windows,
                    "available_count": 0,
                    "busy_count": 0,
                    "total_windows": 0,
                    "rate_limit_status": {
                        "rate_limited_count": 0,
                        "login_required_count": 0,
                        "percentage_limited": 0,
                        "percentage_login_required": 0
                    },
                    "window_details": [],
                    "message": "窗口池未初始化，请点击初始化按钮"
                }
            }
        
        status = autonomous_session_manager.get_pool_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"获取窗口池状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@window_pool_router.post("/initialize")
async def initialize_window_pool():
    """初始化窗口池"""
    try:
        if autonomous_session_manager._initialized:
            return {
                "success": True,
                "message": "窗口池已经初始化"
            }
        
        success = await autonomous_session_manager.initialize_pool()
        if success:
            # 初始化成功后，调用_initialize()启动主循环来处理任务
            start_success = await autonomous_session_manager._initialize()
            if start_success:
                return {
                    "success": True,
                    "message": f"窗口池初始化并启动成功，创建了 {autonomous_session_manager.max_windows} 个窗口，主循环已启动"
                }
            else:
                return {
                    "success": True,
                    "message": f"窗口池初始化成功，创建了 {autonomous_session_manager.max_windows} 个窗口"
                }
        else:
            # 初始化失败，直接提供Chrome启动指导
            detailed_message = {
                "error": "窗口池初始化失败",
                "reason": "Chrome浏览器未以调试模式启动",
                "solution": "请先启动Chrome浏览器：",
                "commands": {
                    "macOS": "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_dev_session",
                    "Windows": "chrome.exe --remote-debugging-port=9222 --user-data-dir=c:\\temp\\chrome_dev_session",
                    "Linux": "google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_dev_session"
                },
                "note": "启动Chrome后，请重新点击初始化按钮"
            }
            raise HTTPException(status_code=500, detail=detailed_message)
    except HTTPException:
        raise  # 重新抛出HTTPException
    except Exception as e:
        error_msg = str(e)
        logger.error(f"初始化窗口池失败: {e}")
        raise HTTPException(status_code=500, detail=f"窗口池初始化失败: {error_msg}")

@window_pool_router.post("/close-all")
async def close_all_windows():
    """关闭所有窗口"""
    try:
        # 关闭所有窗口（重置窗口池）
        await autonomous_session_manager.stop()
        autonomous_session_manager._initialized = False
        return {
            "success": True,
            "message": "所有窗口已关闭"
        }
    except Exception as e:
        logger.error(f"关闭窗口失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@window_pool_router.post("/disconnect")
async def disconnect_window_pool():
    """断开窗口池连接"""
    try:
        # 断开连接
        await autonomous_session_manager.stop()
        return {
            "success": True,
            "message": "窗口池已断开连接"
        }
    except Exception as e:
        logger.error(f"断开连接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@window_pool_router.put("/resize")
async def resize_window_pool(pool_size: int = Query(..., ge=1, le=10)):
    """智能调整窗口池大小"""
    try:
        old_size = autonomous_session_manager.max_windows
        current_windows = len(autonomous_session_manager.available_windows) + len(autonomous_session_manager.busy_windows)
        
        # 更新目标池大小
        autonomous_session_manager.max_windows = pool_size
        
        # 如果已初始化，智能调整窗口数量
        if autonomous_session_manager._initialized:
            await autonomous_session_manager._adjust_window_count()
            
            # 获取调整后的状态
            new_count = len(autonomous_session_manager.available_windows) + len(autonomous_session_manager.busy_windows)
            
            return {
                "success": True,
                "message": f"窗口池大小调整完成",
                "old_size": old_size,
                "new_size": pool_size,
                "previous_windows": current_windows,
                "current_windows": new_count,
                "action_taken": (
                    f"创建了 {new_count - current_windows} 个新窗口" if new_count > current_windows
                    else f"关闭了 {current_windows - new_count} 个窗口" if new_count < current_windows
                    else "窗口数量未变化"
                )
            }
        else:
            # 未初始化，只更新配置
            return {
                "success": True,
                "message": f"窗口池大小配置已更新为 {pool_size}（窗口池未初始化）",
                "old_size": old_size,
                "new_size": pool_size
            }
    except Exception as e:
        logger.error(f"调整窗口池大小失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@window_pool_router.post("/navigate")
async def navigate_window_to_site(window_id: str, url: str):
    """控制指定窗口导航到指定网站"""
    try:
        if not autonomous_session_manager._initialized:
            raise HTTPException(status_code=400, detail="窗口池未初始化")
        
        success = await autonomous_session_manager.navigate_window_to_url(window_id, url)
        
        if success:
            return {
                "success": True,
                "message": f"窗口 {window_id} 成功导航到 {url}"
            }
        else:
            return {
                "success": False,
                "message": f"窗口 {window_id} 导航失败，可能窗口不存在或被封控"
            }
    except Exception as e:
        logger.error(f"窗口导航失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@window_pool_router.get("/site-status")
async def get_window_site_status():
    """获取各窗口的网站封控状态"""
    try:
        # 如果窗口池未初始化，返回空状态
        if not autonomous_session_manager._initialized:
            return {
                "success": True,
                "data": {
                    "windows": [],
                    "summary": {
                        "total_windows": 0,
                        "active_sessions": 0,
                        "total_sites_tracked": 0
                    },
                    "message": "窗口池未初始化，请先在爬虫管理页面初始化"
                }
            }
        
        # 获取窗口池状态
        pool_status = autonomous_session_manager.get_pool_status()
        
        # 获取自主会话管理器的状态
        session_status = await autonomous_session_manager.get_status()
        
        # 组合窗口和网站状态信息
        window_site_status = []
        
        for window in pool_status.get('window_details', []):
            window_id = window.get('window_id')
            
            # 查找对应的会话状态
            session_info = None
            for session in session_status.get('sessions', []):
                if session.get('window_id') == window_id:
                    session_info = session
                    break
            
            # 构建网站状态信息
            site_states = {}
            if session_info and 'site_states' in session_info:
                for site_name, site_state in session_info['site_states'].items():
                    site_states[site_name] = {
                        'status': site_state.get('status', 'unknown'),
                        'blocked_until': site_state.get('blocked_until', 0),
                        'error_count': site_state.get('error_count', 0),
                        'last_success': site_state.get('last_success')
                    }
            
            window_site_status.append({
                'window_id': window_id,
                'window_status': window.get('status'),
                'is_rate_limited': window.get('is_rate_limited', False),
                'site_states': site_states,
                'last_updated': session_info.get('last_activity') if session_info else None
            })
        
        return {
            "success": True,
            "data": {
                "windows": window_site_status,
                "summary": {
                    "total_windows": len(window_site_status),
                    "active_sessions": len(session_status.get('sessions', [])),
                    "total_sites_tracked": len(set().union(*[w.get('site_states', {}).keys() for w in window_site_status]))
                }
            }
        }
    except Exception as e:
        logger.error(f"获取窗口网站状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 任务监控相关路由
@api_router.get("/crawler/status")
async def get_crawler_status():
    """获取爬虫系统状态（包括会话管理器和任务队列）"""
    try:
        # 获取会话管理器状态
        session_manager_status = await autonomous_session_manager.get_status()
        
        # 获取数据库中的任务统计
        from ..models.repositories import CrawlTaskRepository
        task_repo = CrawlTaskRepository()
        
        # 检查方法是否存在（热重载兼容）
        if hasattr(task_repo, 'get_task_statistics'):
            db_task_stats = task_repo.get_task_statistics()
        else:
            # 降级方案：手动查询统计
            from ..models.database import db
            query = """
                SELECT status, COUNT(*) as count
                FROM crawl_tasks
                GROUP BY status
            """
            results = db.execute_query(query)
            
            # 转换为字典格式
            db_task_stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
            for row in results:
                status = row["status"]
                count = row["count"]
                if status == "pending":
                    db_task_stats["pending"] = count
                elif status in ["running", "in_progress"]:
                    db_task_stats["running"] = count
                elif status == "completed":
                    db_task_stats["completed"] = count
                elif status == "failed":
                    db_task_stats["failed"] = count
        
        return {
            "success": True,
            "data": {
                "session_manager": session_manager_status,
                "task_queue": {
                    # 内存队列状态（来自会话管理器）
                    "memory_queue_size": session_manager_status.get("queue_size", 0),
                    "processing_count": session_manager_status.get("processing_tasks", 0),
                    # 数据库任务统计
                    "total_pending": db_task_stats.get("pending", 0),
                    "total_running": db_task_stats.get("running", 0),
                    "total_completed": db_task_stats.get("completed", 0),
                    "total_failed": db_task_stats.get("failed", 0)
                }
            }
        }
    except Exception as e:
        logger.error(f"获取爬虫状态失败: {e}")
        return {
            "success": False,
            "data": {
                "session_manager": {"running": False, "error": str(e)},
                "task_queue": {"total_pending": 0, "total_running": 0, "error": str(e)}
            }
        }

@api_router.get("/crawler/tasks/recent")
async def get_recent_tasks(limit: int = Query(20, ge=1, le=100)):
    """获取最近的任务列表"""
    try:
        tasks = task_repo.get_recent_tasks(limit)
        
        # 转换为前端需要的格式
        formatted_tasks = []
        for task in tasks:
            formatted_tasks.append({
                "id": task.get("id"),
                "task_type": task.get("task_type"),
                "target_isbn": task.get("target_isbn"),
                "target_url": task.get("target_url"),
                "book_title": task.get("book_title"),
                "status": task.get("status"),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
                "end_time": task.get("end_time"),  # 添加任务完成时间
                "error_message": task.get("error_message")
            })
        
        return {
            "success": True,
            "data": formatted_tasks
        }
    except Exception as e:
        logger.error(f"获取最近任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/crawler/tasks/isbn-analysis")
async def create_isbn_analysis_task(request_data: dict):
    """创建ISBN分析任务"""
    try:
        isbn = request_data.get("isbn")
        quality = request_data.get("quality", "high")
        
        if not isbn:
            raise HTTPException(status_code=422, detail="ISBN不能为空")
        
        # 创建ISBN分析任务
        task_id = crawler_service_v2.add_isbn_analysis_task(isbn, priority=9)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"ISBN分析任务已创建，任务ID: {task_id}"
        }
    except Exception as e:
        logger.error(f"创建ISBN分析任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
