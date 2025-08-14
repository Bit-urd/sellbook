#!/usr/bin/env python3
"""
店铺管理路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import logging

from ..models.repositories import ShopRepository, BookRepository, SalesRepository
from ..models.models import Shop
from ..services.crawler_service import KongfuziCrawler
from ..models.database import db

logger = logging.getLogger(__name__)

# 创建路由
shop_router = APIRouter(prefix="/api/shops", tags=["shops"])

# 仓库实例
shop_repo = ShopRepository()
book_repo = BookRepository()
sales_repo = SalesRepository()

class ShopCreateRequest(BaseModel):
    """创建店铺请求"""
    shop_id: str
    shop_name: str
    platform: str = 'kongfuzi'
    shop_url: Optional[str] = None
    shop_type: Optional[str] = None

class ShopUpdateRequest(BaseModel):
    """更新店铺请求"""
    shop_name: Optional[str] = None
    shop_url: Optional[str] = None
    shop_type: Optional[str] = None
    status: Optional[str] = None

@shop_router.get("")
async def get_shops(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None
):
    """获取店铺列表（支持搜索和分页）"""
    try:
        offset = (page - 1) * page_size
        
        # 获取店铺列表并计算爬取状态
        query = """
            SELECT 
                s.*,
                COUNT(DISTINCT b.isbn) as total_books,
                COUNT(DISTINCT CASE WHEN b.is_crawled = 0 THEN b.isbn END) as uncrawled_books,
                COUNT(DISTINCT CASE WHEN b.is_crawled = 1 THEN b.isbn END) as crawled_books,
                MAX(b.last_sales_update) as last_update
            FROM shops s
            LEFT JOIN sales_records sr ON s.id = sr.shop_id
            LEFT JOIN books b ON sr.isbn = b.isbn
        """
        
        params = []
        where_clauses = []
        
        if search:
            where_clauses.append("(s.shop_id LIKE ? OR s.shop_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " GROUP BY s.id ORDER BY s.created_at DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        shops = db.execute_query(query, tuple(params))
        
        # 获取总数
        count_query = "SELECT COUNT(*) as total FROM shops"
        if search:
            count_query += " WHERE shop_id LIKE ? OR shop_name LIKE ?"
            total = db.execute_query(count_query, (f"%{search}%", f"%{search}%"))[0]['total']
        else:
            total = db.execute_query(count_query)[0]['total']
        
        # 计算爬取状态
        for shop in shops:
            shop['crawl_status'] = 'not_started' if shop['total_books'] == 0 else \
                                  'completed' if shop['uncrawled_books'] == 0 else \
                                  'partial'
            shop['crawl_progress'] = 0 if shop['total_books'] == 0 else \
                                    round((shop['crawled_books'] / shop['total_books']) * 100, 2)
        
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

@shop_router.get("/{shop_id}")
async def get_shop(shop_id: str):
    """获取单个店铺详情"""
    try:
        shop = shop_repo.get_by_shop_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        # 获取店铺统计
        stats = db.execute_query("""
            SELECT 
                COUNT(DISTINCT b.isbn) as total_books,
                COUNT(DISTINCT CASE WHEN b.is_crawled = 0 THEN b.isbn END) as uncrawled_books,
                COUNT(DISTINCT sr.id) as total_sales,
                AVG(sr.sale_price) as avg_price,
                MAX(b.last_sales_update) as last_update
            FROM shops s
            LEFT JOIN sales_records sr ON s.id = sr.shop_id
            LEFT JOIN books b ON sr.isbn = b.isbn
            WHERE s.shop_id = ?
        """, (shop_id,))
        
        shop['statistics'] = stats[0] if stats else {}
        
        return {"success": True, "data": shop}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取店铺详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@shop_router.post("")
async def create_shop(request: ShopCreateRequest):
    """创建新店铺"""
    try:
        # 检查店铺是否已存在
        existing = shop_repo.get_by_shop_id(request.shop_id)
        if existing:
            raise HTTPException(status_code=400, detail="店铺已存在")
        
        shop = Shop(
            shop_id=request.shop_id,
            shop_name=request.shop_name,
            platform=request.platform,
            shop_url=request.shop_url,
            shop_type=request.shop_type
        )
        
        shop_id = shop_repo.create(shop)
        
        return {
            "success": True,
            "message": "店铺创建成功",
            "data": {"id": shop_id, "shop_id": request.shop_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@shop_router.put("/{shop_id}")
async def update_shop(shop_id: str, request: ShopUpdateRequest):
    """更新店铺信息"""
    try:
        shop = shop_repo.get_by_shop_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        update_fields = []
        params = []
        
        if request.shop_name is not None:
            update_fields.append("shop_name = ?")
            params.append(request.shop_name)
        
        if request.shop_url is not None:
            update_fields.append("shop_url = ?")
            params.append(request.shop_url)
        
        if request.shop_type is not None:
            update_fields.append("shop_type = ?")
            params.append(request.shop_type)
        
        if request.status is not None:
            update_fields.append("status = ?")
            params.append(request.status)
        
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE shops SET {', '.join(update_fields)} WHERE shop_id = ?"
            params.append(shop_id)
            
            db.execute_update(query, tuple(params))
        
        return {"success": True, "message": "店铺更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@shop_router.delete("/{shop_id}")
async def delete_shop(shop_id: str):
    """删除店铺"""
    try:
        shop = shop_repo.get_by_shop_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        # 删除相关数据
        db.execute_update("DELETE FROM sales_records WHERE shop_id = ?", (shop['id'],))
        db.execute_update("DELETE FROM book_inventory WHERE shop_id = ?", (shop['id'],))
        db.execute_update("DELETE FROM shops WHERE id = ?", (shop['id'],))
        
        return {"success": True, "message": "店铺删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@shop_router.post("/{shop_id}/crawl")
async def crawl_shop_books(shop_id: str, incremental: bool = Query(False)):
    """爬取店铺书籍（支持增量爬取）"""
    try:
        shop = shop_repo.get_by_shop_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        
        crawler = KongfuziCrawler()
        
        if incremental:
            # 增量爬取：只爬取未爬取的书籍
            uncrawled_books = db.execute_query("""
                SELECT DISTINCT b.isbn, b.title
                FROM books b
                JOIN sales_records sr ON b.isbn = sr.isbn
                WHERE sr.shop_id = ? AND b.is_crawled = 0
            """, (shop['id'],))
            
            crawled_count = 0
            for book in uncrawled_books:
                try:
                    await crawler.crawl_book_sales(book['isbn'])
                    crawled_count += 1
                    
                    # 更新书籍状态
                    db.execute_update("""
                        UPDATE books 
                        SET is_crawled = 1, 
                            last_sales_update = CURRENT_TIMESTAMP
                        WHERE isbn = ?
                    """, (book['isbn'],))
                except Exception as e:
                    logger.error(f"爬取书籍 {book['isbn']} 失败: {e}")
            
            return {
                "success": True,
                "message": f"增量爬取完成，共爬取 {crawled_count}/{len(uncrawled_books)} 本书籍",
                "data": {
                    "crawled": crawled_count,
                    "total": len(uncrawled_books)
                }
            }
        else:
            # 全量爬取
            sales_count = await crawler.crawl_shop_sales(shop_id)
            
            # 更新所有相关书籍状态
            db.execute_update("""
                UPDATE books 
                SET is_crawled = 1, 
                    last_sales_update = CURRENT_TIMESTAMP
                WHERE isbn IN (
                    SELECT DISTINCT isbn 
                    FROM sales_records 
                    WHERE shop_id = ?
                )
            """, (shop['id'],))
            
            return {
                "success": True,
                "message": f"全量爬取完成，共爬取 {sales_count} 条销售记录",
                "data": {"sales_count": sales_count}
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"爬取店铺失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@shop_router.post("/batch-crawl")
async def batch_crawl_shops(
    shop_ids: List[str],
    incremental: bool = Query(False)
):
    """批量爬取多个店铺"""
    try:
        results = []
        
        for shop_id in shop_ids:
            try:
                shop = shop_repo.get_by_shop_id(shop_id)
                if not shop:
                    results.append({
                        "shop_id": shop_id,
                        "success": False,
                        "message": "店铺不存在"
                    })
                    continue
                
                crawler = KongfuziCrawler()
                
                if incremental:
                    # 增量爬取逻辑
                    uncrawled_books = db.execute_query("""
                        SELECT DISTINCT b.isbn
                        FROM books b
                        JOIN sales_records sr ON b.isbn = sr.isbn
                        WHERE sr.shop_id = ? AND b.is_crawled = 0
                    """, (shop['id'],))
                    
                    crawled_count = 0
                    for book in uncrawled_books:
                        try:
                            await crawler.crawl_book_sales(book['isbn'])
                            crawled_count += 1
                            db.execute_update("""
                                UPDATE books 
                                SET is_crawled = 1, 
                                    last_sales_update = CURRENT_TIMESTAMP
                                WHERE isbn = ?
                            """, (book['isbn'],))
                        except:
                            pass
                    
                    results.append({
                        "shop_id": shop_id,
                        "success": True,
                        "message": f"增量爬取 {crawled_count} 本书籍"
                    })
                else:
                    # 全量爬取
                    sales_count = await crawler.crawl_shop_sales(shop_id)
                    results.append({
                        "shop_id": shop_id,
                        "success": True,
                        "message": f"全量爬取 {sales_count} 条记录"
                    })
                    
            except Exception as e:
                results.append({
                    "shop_id": shop_id,
                    "success": False,
                    "message": str(e)
                })
        
        return {
            "success": True,
            "message": f"批量爬取完成",
            "data": results
        }
    except Exception as e:
        logger.error(f"批量爬取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))