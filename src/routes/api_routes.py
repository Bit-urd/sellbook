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

@api_router.post("/book/analyze")
async def analyze_book_sales(isbn: str):
    """实时分析单本书的销售数据（ISBN搜索）"""
    try:
        # 验证ISBN格式
        isbn = isbn.strip()
        if not isbn or len(isbn) < 10:
            raise HTTPException(status_code=400, detail="请输入有效的ISBN号码")
        
        # 使用爬虫实时获取销售数据
        crawler = KongfuziCrawler()
        stats = await crawler.analyze_book_sales(isbn, days_limit=30)
        
        # 构建响应
        response = {
            "isbn": isbn,
            "stats": {
                "sales_1_day": stats.get("sales_1_day", 0),
                "sales_7_days": stats.get("sales_7_days", 0),
                "sales_30_days": stats.get("sales_30_days", 0),
                "total_records": stats.get("total_records", 0),
                "latest_sale_date": stats.get("latest_sale_date"),
                "average_price": stats.get("average_price"),
                "price_range": stats.get("price_range"),
            },
            "message": "分析完成",
            "success": True
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析书籍销售数据失败: {e}")
        return {
            "isbn": isbn,
            "stats": {
                "sales_1_day": 0,
                "sales_7_days": 0,
                "sales_30_days": 0,
                "total_records": 0,
                "latest_sale_date": None,
                "average_price": None,
                "price_range": None
            },
            "message": f"分析失败: {str(e)}",
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
