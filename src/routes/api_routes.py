#!/usr/bin/env python3
"""
API路由定义
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from datetime import datetime
import logging

from ..services.analysis_service import AnalysisService
from ..services.crawler_service import CrawlerManager, KongfuziCrawler, DuozhuayuCrawler
from ..models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository,
    SalesRepository, CrawlTaskRepository
)
from ..models.models import Shop, CrawlTask

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
    limit: int = Query(20, ge=1, le=100)
):
    """获取热销排行榜"""
    try:
        hot_sales = analysis_service.get_hot_sales_ranking(days, limit)
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
async def get_profitable_items(min_margin: float = Query(20.0, ge=0, le=100)):
    """获取有利润的商品"""
    try:
        items = analysis_service.get_profitable_items(min_margin)
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
        
        # 使用爬虫实时获取销售数据
        crawler = KongfuziCrawler()
        stats = await crawler.analyze_book_sales(isbn, days_limit=30, quality_filter=quality)
        
        # 构建响应
        response = {
            "isbn": isbn,
            "stats": {
                "sales_3_days": stats.get("sales_3_days", 0),
                "sales_7_days": stats.get("sales_7_days", 0),
                "sales_30_days": stats.get("sales_30_days", 0),
                "total_records": stats.get("total_records", 0),
                "latest_sale_date": stats.get("latest_sale_date"),
                "average_price": stats.get("average_price"),
                "price_range": stats.get("price_range"),
                "sales_records": stats.get("sales_records", []),
            },
            "message": "分析完成",
            "success": True
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析书籍销售数据失败: {e}")
        
        # 根据不同错误类型返回用户友好的错误信息
        error_message = "分析失败"
        error_str = str(e)
        
        if "Cannot connect to host localhost:9222" in error_str:
            error_message = "爬虫服务暂时不可用，请稍后再试"
        elif "Chrome" in error_str or "browser" in error_str.lower():
            error_message = "数据抓取服务暂时不可用"
        elif "timeout" in error_str.lower():
            error_message = "请求超时，请稍后再试"
        elif "network" in error_str.lower() or "connection" in error_str.lower():
            error_message = "网络连接异常，请检查网络后重试"
        else:
            error_message = f"分析失败: {error_str}"
        
        return {
            "isbn": isbn,
            "stats": {
                "sales_3_days": 0,
                "sales_7_days": 0,
                "sales_30_days": 0,
                "total_records": 0,
                "latest_sale_date": None,
                "average_price": None,
                "price_range": None
            },
            "message": error_message,
            "success": False
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
        
        # 异步执行爬虫
        crawler = KongfuziCrawler()
        books_count = await crawler.crawl_shop_books(shop_id, max_pages)
        
        return {
            "success": True,
            "message": f"成功爬取 {books_count} 本书籍",
            "task_id": task_id
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
        await crawler_manager.run_pending_tasks()
        return {"success": True, "message": "任务执行已启动"}
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
        
        # 异步执行爬虫
        crawler = KongfuziCrawler()
        sales_count = await crawler.crawl_shop_sales(shop_id)
        
        return {
            "success": True,
            "message": f"成功爬取 {sales_count} 条销售记录",
            "task_id": task_id,
            "shop_id": shop_id
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
        
        # 启动爬虫任务
        await crawler_manager.run_pending_tasks()
        
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

@sales_data_router.get("/books/crawl-status")
async def get_books_crawl_status(
    status: str = Query("all", regex="^(all|crawled|not_crawled)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取书籍爬取状态"""
    try:
        from ..models.database import db
        
        # 构建查询条件
        where_clause = ""
        if status == "crawled":
            where_clause = "WHERE last_sales_update IS NOT NULL"
        elif status == "not_crawled":
            where_clause = "WHERE last_sales_update IS NULL"
        
        # 获取总数
        total_query = f"SELECT COUNT(*) as total FROM books {where_clause}"
        total_result = db.execute_query(total_query)
        total = total_result[0]['total'] if total_result else 0
        
        # 获取分页数据
        offset = (page - 1) * page_size
        books_query = f"""
            SELECT 
                isbn, title, author, publisher,
                last_sales_update,
                created_at, updated_at
            FROM books
            {where_clause}
            ORDER BY last_sales_update DESC NULLS LAST
            LIMIT ? OFFSET ?
        """
        books = db.execute_query(books_query, (page_size, offset))
        
        # 统计信息
        stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_books,
                SUM(CASE WHEN last_sales_update IS NOT NULL THEN 1 ELSE 0 END) as crawled_count,
                SUM(CASE WHEN last_sales_update IS NULL THEN 1 ELSE 0 END) as not_crawled_count
            FROM books
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
        logger.error(f"获取书籍爬取状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
