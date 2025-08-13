#!/usr/bin/env python3
"""
书籍销售分析API
FastAPI接口，提供基于ISBN的书籍销售数据分析
"""
import asyncio
import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
import re

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
import aiohttp

# 全局变量存储浏览器连接
browser_manager = None

class BookAnalysisRequest(BaseModel):
    book_isbn: str

class SalesStats(BaseModel):
    sales_1_day: int
    sales_7_days: int
    sales_30_days: int
    total_records: int
    latest_sale_date: Optional[str]
    average_price: Optional[float]
    price_range: Optional[Dict[str, float]]

class AnalysisResponse(BaseModel):
    isbn: str
    stats: SalesStats
    message: str
    success: bool

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.connected = False

    async def connect_to_chrome(self):
        """连接到现有的Chrome调试会话"""
        if self.connected:
            return True
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                    else:
                        return False
        except:
            return False
        
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
            
            # 使用现有浏览器上下文
            contexts = self.browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await self.browser.new_context()
            
            # 使用现有页面或创建新页面
            pages = context.pages
            if pages:
                self.page = pages[0]
            else:
                self.page = await context.new_page()
            
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Chrome连接失败: {e}")
            return False

    async def analyze_book_sales(self, isbn: str, days_limit: int = 30) -> List[Dict]:
        """分析单本书的销售记录"""
        if not self.connected:
            if not await self.connect_to_chrome():
                raise HTTPException(status_code=500, detail="无法连接到Chrome浏览器")
        
        # 构建搜索URL
        search_url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1&actionPath=sortType,quality&quality=90~&quaSelect=2"
        
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        all_sales = []
        
        try:
            await self.page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            page_num = 1
            max_pages = 20
            
            while page_num <= max_pages:
                await asyncio.sleep(1)
                
                # 提取当前页面的销售记录
                page_sales = await self.extract_sales_records()
                
                if not page_sales:
                    break
                
                # 检查时间限制
                has_old_records = False
                valid_sales = []
                
                for sale in page_sales:
                    sale_date = self.parse_sale_date(sale.get('sold_time', ''))
                    if sale_date and sale_date >= cutoff_date:
                        sale['book_isbn'] = isbn
                        sale['sale_date'] = sale_date
                        valid_sales.append(sale)
                    else:
                        has_old_records = True
                
                if valid_sales:
                    all_sales.extend(valid_sales)
                
                # 如果发现超过时间限制的记录，停止翻页
                if has_old_records:
                    break
                
                # 尝试翻到下一页
                if not await self.go_to_next_page():
                    break
                
                page_num += 1
                await asyncio.sleep(2)
            
            return all_sales
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"爬取数据失败: {str(e)}")

    async def extract_sales_records(self):
        """提取当前页面的销售记录"""
        try:
            return await self.page.evaluate("""
                () => {
                    const sales = [];
                    const productItems = document.querySelectorAll('.product-item-wrap');
                    
                    productItems.forEach(item => {
                        try {
                            const record = {};
                            
                            // 提取售出时间
                            const soldTimeElement = item.querySelector('.sold-time');
                            if (soldTimeElement) {
                                record.sold_time = soldTimeElement.textContent.trim();
                            }
                            
                            // 提取价格信息
                            const priceElement = item.querySelector('.price-info');
                            if (priceElement) {
                                const priceInt = item.querySelector('.price-int');
                                const priceFloat = item.querySelector('.price-float');
                                if (priceInt && priceFloat) {
                                    record.price = priceInt.textContent + '.' + priceFloat.textContent;
                                }
                            }
                            
                            // 提取品相
                            const qualityElement = item.querySelector('.quality-info');
                            if (qualityElement) {
                                record.quality = qualityElement.textContent.trim();
                            }
                            
                            // 只保留有售出时间的记录
                            if (record.sold_time && record.sold_time.includes('已售')) {
                                sales.push(record);
                            }
                            
                        } catch (error) {
                            console.log('提取销售记录时出错:', error);
                        }
                    });
                    
                    return sales;
                }
            """)
        except:
            return []

    def parse_sale_date(self, sold_time: str) -> Optional[datetime]:
        """解析售出时间字符串"""
        try:
            if not sold_time or '已售' not in sold_time:
                return None
            
            date_str = sold_time.replace(' 已售', '').strip()
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return None

    async def go_to_next_page(self):
        """翻到下一页"""
        try:
            next_selectors = [
                '.pagination .next:not(.disabled)',
                '.pagination a[title="下一页"]',
                '.page-next:not(.disabled)',
                'a:has-text("下一页"):not(.disabled)'
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = await self.page.query_selector(selector)
                    if next_btn:
                        await next_btn.click()
                        await self.page.wait_for_load_state('networkidle')
                        return True
                except:
                    continue
            
            return False
        except:
            return False

    async def close(self):
        """关闭连接"""
        if self.playwright:
            await self.playwright.stop()
        self.connected = False

# 初始化FastAPI应用
app = FastAPI(
    title="书籍销售分析API",
    description="基于孔夫子旧书网的书籍销售数据分析接口",
    version="1.0.0"
)

# 初始化浏览器管理器
browser_manager = BrowserManager()

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

def save_to_csv(sales_data: List[Dict], isbn: str):
    """将销售数据追加到CSV文件"""
    csv_file = "api_sales_data.csv"
    fieldnames = ['book_isbn', 'sale_date', 'sold_time', 'price', 'quality', 'analyzed_at']
    
    # 检查文件是否存在，不存在则创建并写入表头
    file_exists = os.path.exists(csv_file)
    
    try:
        with open(csv_file, 'a', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            current_time = datetime.now().isoformat()
            for sale in sales_data:
                row = {
                    'book_isbn': sale.get('book_isbn', isbn),
                    'sale_date': sale.get('sale_date', '').strftime('%Y-%m-%d') if sale.get('sale_date') else '',
                    'sold_time': sale.get('sold_time', ''),
                    'price': sale.get('price', ''),
                    'quality': sale.get('quality', ''),
                    'analyzed_at': current_time
                }
                writer.writerow(row)
                
    except Exception as e:
        print(f"保存CSV失败: {e}")

def analyze_sales_data(sales_data: List[Dict]) -> SalesStats:
    """分析销售数据，生成统计信息"""
    if not sales_data:
        return SalesStats(
            sales_1_day=0,
            sales_7_days=0,
            sales_30_days=0,
            total_records=0,
            latest_sale_date=None,
            average_price=None,
            price_range=None
        )
    
    now = datetime.now()
    one_day_ago = now - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    sales_1_day = 0
    sales_7_days = 0
    sales_30_days = 0
    
    prices = []
    latest_date = None
    
    for sale in sales_data:
        sale_date = sale.get('sale_date')
        if not sale_date:
            continue
        
        # 统计不同时间段的销量
        if sale_date >= one_day_ago:
            sales_1_day += 1
        if sale_date >= seven_days_ago:
            sales_7_days += 1
        if sale_date >= thirty_days_ago:
            sales_30_days += 1
        
        # 收集价格数据
        try:
            price = float(sale.get('price', 0))
            if price > 0:
                prices.append(price)
        except:
            pass
        
        # 找到最新销售日期
        if latest_date is None or sale_date > latest_date:
            latest_date = sale_date
    
    # 计算价格统计
    average_price = sum(prices) / len(prices) if prices else None
    price_range = {
        'min': min(prices),
        'max': max(prices)
    } if prices else None
    
    return SalesStats(
        sales_1_day=sales_1_day,
        sales_7_days=sales_7_days,
        sales_30_days=sales_30_days,
        total_records=len(sales_data),
        latest_sale_date=latest_date.strftime('%Y-%m-%d') if latest_date else None,
        average_price=round(average_price, 2) if average_price else None,
        price_range=price_range
    )

@app.get("/")
async def root():
    """返回主页"""
    return FileResponse('static/index.html')

@app.get("/health")
async def health_check():
    """健康检查接口"""
    chrome_connected = browser_manager.connected
    if not chrome_connected:
        chrome_connected = await browser_manager.connect_to_chrome()
    
    return {
        "status": "healthy" if chrome_connected else "chrome_disconnected",
        "chrome_connected": chrome_connected,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_book(request: BookAnalysisRequest):
    """分析书籍销售数据"""
    isbn = request.book_isbn.strip()
    
    if not isbn:
        raise HTTPException(status_code=400, detail="ISBN不能为空")
    
    try:
        # 爬取销售数据
        sales_data = await browser_manager.analyze_book_sales(isbn, days_limit=30)
        
        # 保存到CSV
        if sales_data:
            save_to_csv(sales_data, isbn)
        
        # 分析数据
        stats = analyze_sales_data(sales_data)
        
        return AnalysisResponse(
            isbn=isbn,
            stats=stats,
            message=f"成功分析ISBN {isbn}，找到 {len(sales_data)} 条销售记录",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理工作"""
    if browser_manager:
        await browser_manager.close()

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 启动书籍销售分析API服务...")
    print("📖 API文档地址: http://localhost:8000/docs")
    print("🔍 健康检查: http://localhost:8000/health")
    
    uvicorn.run(
        "book_analysis_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )