#!/usr/bin/env python3
"""
爬虫服务模块 - 负责数据抓取逻辑
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from playwright.async_api import async_playwright, Page

from ..models.models import Shop, Book, BookInventory, SalesRecord, CrawlTask
from ..models.repositories import (
    ShopRepository, BookRepository, BookInventoryRepository, 
    SalesRepository, CrawlTaskRepository
)

logger = logging.getLogger(__name__)

class KongfuziCrawler:
    """孔夫子网爬虫"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.connected = False
        self.shop_repo = ShopRepository()
        self.book_repo = BookRepository()
        self.inventory_repo = BookInventoryRepository()
        self.sales_repo = SalesRepository()
        self.task_repo = CrawlTaskRepository()
    
    async def connect_browser(self):
        """连接到Chrome浏览器"""
        if self.connected:
            return True
        
        try:
            # 尝试连接到已打开的Chrome调试端口
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                    else:
                        logger.error("无法获取Chrome调试信息")
                        return False
            
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
            logger.info("成功连接到Chrome浏览器")
            return True
            
        except Exception as e:
            logger.error(f"Chrome连接失败: {e}")
            return False
    
    async def disconnect_browser(self):
        """断开浏览器连接"""
        if self.playwright:
            await self.playwright.stop()
            self.connected = False
    
    async def crawl_shop_books(self, shop_id: str, max_pages: int = 50) -> int:
        """爬取店铺的书籍列表"""
        if not await self.connect_browser():
            raise Exception("无法连接到浏览器")
        
        # 创建爬虫任务
        task = CrawlTask(
            task_name=f"爬取店铺 {shop_id} 的书籍",
            task_type="shop_books",
            target_platform="kongfuzi",
            target_url=f"https://shop.kongfz.com/{shop_id}/all/0_50_0_0_1_newItem_desc_0_0/",
            status="running"
        )
        task_id = self.task_repo.create(task)
        
        try:
            books_crawled = 0
            current_page = 1
            
            # 访问店铺首页
            url = f"https://shop.kongfz.com/{shop_id}/all/0_50_0_0_1_newItem_desc_0_0/"
            await self.page.goto(url, wait_until='networkidle')
            await asyncio.sleep(2)  # 等待页面加载
            
            while current_page <= max_pages:
                try:
                    # 提取书籍信息
                    books_data = await self.page.evaluate("""
                    () => {
                        const items = [];
                        // 查找item-row元素，它包含了itemid和isbn属性
                        document.querySelectorAll('.item-row').forEach(item => {
                            const titleEl = item.querySelector('.row-name');
                            const authorEl = item.querySelector('.row-author');
                            const pressEl = item.querySelector('.row-press');
                            const priceEl = item.querySelector('.row-price');
                            const qualityEl = item.querySelector('.row-quality');
                            
                            // 获取item的属性
                            const itemId = item.getAttribute('itemid');
                            const isbn = item.getAttribute('isbn');
                            const shopId = item.getAttribute('shopid');
                            
                            if (titleEl) {
                                // 处理价格，移除所有货币符号
                                let price = '';
                                if (priceEl) {
                                    const boldPrice = priceEl.querySelector('.bold');
                                    if (boldPrice) {
                                        price = boldPrice.textContent.trim();
                                    } else {
                                        price = priceEl.textContent
                                            .replace(/[¥￥]/g, '')  // 移除半角和全角￥
                                            .replace(/[^\d.]/g, '')  // 只保留数字和小数点
                                            .trim();
                                    }
                                }
                                
                                items.push({
                                    title: titleEl.textContent.trim(),
                                    url: titleEl.href,
                                    author: authorEl ? authorEl.textContent.trim() : '',
                                    publisher: pressEl ? pressEl.textContent.trim() : '',
                                    price: price,
                                    quality: qualityEl ? qualityEl.textContent.trim() : '',
                                    itemId: itemId || '',
                                    isbn: isbn || '',
                                    shopId: shopId || ''
                                });
                            }
                        });
                        
                        // 如果item-row选择器没有找到元素，尝试使用.item选择器（兼容旧版页面）
                        if (items.length === 0) {
                            document.querySelectorAll('.item').forEach(item => {
                                const titleEl = item.querySelector('.title a');
                                const priceEl = item.querySelector('.price');
                                const qualityEl = item.querySelector('.quality');
                                
                                if (titleEl) {
                                    let price = '';
                                    if (priceEl) {
                                        price = priceEl.textContent
                                            .replace(/[¥￥]/g, '')
                                            .replace(/[^\d.]/g, '')
                                            .trim();
                                    }
                                    
                                    // 从URL提取ID作为备用
                                    let bookId = '';
                                    if (titleEl.href) {
                                        const matches = titleEl.href.match(/\/(\d+)\/(\d+)\//);
                                        if (matches && matches[2]) {
                                            bookId = matches[2];
                                        }
                                    }
                                    
                                    items.push({
                                        title: titleEl.textContent.trim(),
                                        url: titleEl.href,
                                        author: '',
                                        publisher: '',
                                        price: price,
                                        quality: qualityEl ? qualityEl.textContent.trim() : '',
                                        itemId: bookId,
                                        isbn: '',
                                        shopId: ''
                                    });
                                }
                            });
                        }
                        
                        return items;
                    }
                """)
                    
                    if not books_data:
                        logger.info(f"第 {current_page} 页没有书籍数据")
                        break
                    
                    # 保存书籍数据
                    for book_data in books_data:
                        # 优先使用真实的ISBN，如果没有则使用itemId作为唯一标识
                        isbn = book_data.get('isbn') or book_data.get('itemId')
                        if not isbn:
                            logger.warning(f"无法获取书籍唯一标识: {book_data['title']}")
                            continue
                        
                        # 创建或更新书籍
                        book = Book(
                            isbn=isbn,  # 使用真实ISBN或itemId作为唯一标识
                            title=book_data['title'],
                            author=book_data.get('author'),
                            publisher=book_data.get('publisher')
                        )
                        book_isbn = self.book_repo.create_or_update(book)
                        
                        if not book_isbn:
                            logger.error(f"无法保存书籍: {book_data['title']}")
                            continue
                        
                        # 获取店铺信息
                        shop_info = self.shop_repo.get_by_id(shop_id)
                        if not shop_info:
                            continue
                        
                        # 安全解析价格
                        price = None
                        if book_data['price']:
                            try:
                                price = float(book_data['price'])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"无法解析价格 '{book_data['price']}': {e}")
                                price = None
                        
                        # 创建库存记录
                        inventory = BookInventory(
                            isbn=book_isbn,
                            shop_id=shop_info['id'],
                            kongfuzi_price=price,
                            kongfuzi_condition=book_data.get('quality'),
                            kongfuzi_book_url=book_data.get('url'),
                            kongfuzi_item_id=book_data.get('itemId')  # 保存原始的itemId
                        )
                        self.inventory_repo.upsert(inventory)
                        books_crawled += 1
                    
                    logger.info(f"第 {current_page} 页爬取了 {len(books_data)} 本书籍")
                    
                    # 更新任务进度
                    progress = (current_page / max_pages) * 100
                    self.task_repo.update_status(task_id, 'running', progress)
                    
                    # 检查是否有下一页
                    has_next_page = await self.page.evaluate("""
                        () => {
                            // 查找下一页按钮，可能有多种selector
                            const nextBtn = document.querySelector('.next-btn') || 
                                           document.querySelector('.pagination .next') ||
                                           document.querySelector('a[title="下一页"]') ||
                                           document.querySelector('.page-next:not(.disabled)');
                            return nextBtn && !nextBtn.classList.contains('disabled') && 
                                   !nextBtn.classList.contains('inactive');
                        }
                    """)
                    
                    if not has_next_page or current_page >= max_pages:
                        logger.info(f"没有下一页或已达到最大页数限制 {max_pages}")
                        break
                    
                    # 点击下一页
                    await self.page.evaluate("""
                        () => {
                            const nextBtn = document.querySelector('.next-btn') || 
                                           document.querySelector('.pagination .next') ||
                                           document.querySelector('a[title="下一页"]') ||
                                           document.querySelector('.page-next:not(.disabled)');
                            if (nextBtn) nextBtn.click();
                        }
                    """)
                    
                    # 等待新页面加载
                    await asyncio.sleep(3)
                    
                    # 等待页面稳定
                    try:
                        await self.page.wait_for_load_state('networkidle', timeout=5000)
                    except:
                        # 如果等待超时，继续执行
                        pass
                    
                    current_page += 1
                    
                except Exception as e:
                    logger.warning(f"第 {current_page} 页处理出错: {e}")
                    # 如果出错，尝试继续下一页
                    current_page += 1
                    if current_page > max_pages:
                        break
                    # 等待一下再继续
                    await asyncio.sleep(3)
                    continue
            
            # 更新任务为完成
            self.task_repo.update_status(task_id, 'completed', 100)
            logger.info(f"成功爬取店铺 {shop_id} 的 {books_crawled} 本书籍")
            return books_crawled
            
        except Exception as e:
            logger.error(f"爬取店铺失败: {e}")
            self.task_repo.update_status(task_id, 'failed', error_message=str(e))
            raise
    
    async def crawl_book_sales(self, isbn: str, days_limit: int = 30) -> List[Dict]:
        """爬取书籍的销售记录"""
        if not await self.connect_browser():
            raise Exception("无法连接到浏览器")
        
        url = f"https://search.kongfz.com/product/?keyword={isbn}&dataType=1&sortType=10&page=1"
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        all_sales = []
        
        try:
            await self.page.goto(url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 提取已售记录
            sales_data = await self.page.evaluate("""
                () => {
                    const sales = [];
                    document.querySelectorAll('.sold-item').forEach(item => {
                        const priceEl = item.querySelector('.price');
                        const dateEl = item.querySelector('.date');
                        const qualityEl = item.querySelector('.quality');
                        
                        if (priceEl && dateEl) {
                            sales.push({
                                price: priceEl.textContent.replace('¥', '').trim(),
                                date: dateEl.textContent.trim(),
                                quality: qualityEl ? qualityEl.textContent.trim() : ''
                            });
                        }
                    });
                    return sales;
                }
            """)
            
            # 获取书籍信息
            book = self.book_repo.get_by_isbn(isbn)
            if not book:
                logger.warning(f"找不到ISBN为 {isbn} 的书籍")
                return []
            
            # 保存销售记录
            sales_records = []
            for sale in sales_data:
                try:
                    sale_date = datetime.strptime(sale['date'], '%Y-%m-%d')
                    if sale_date < cutoff_date:
                        continue
                    
                    record = SalesRecord(
                        isbn=isbn,  # 使用ISBN作为外键
                        shop_id=1,  # 默认店铺ID，实际应该从页面获取
                        sale_price=float(sale['price']),
                        sale_date=sale_date,
                        book_condition=sale['quality']
                    )
                    sales_records.append(record)
                    all_sales.append(sale)
                except Exception as e:
                    logger.error(f"处理销售记录失败: {e}")
                    continue
            
            if sales_records:
                self.sales_repo.batch_create(sales_records)
            
            logger.info(f"成功爬取 {isbn} 的 {len(all_sales)} 条销售记录")
            return all_sales
            
        except Exception as e:
            logger.error(f"爬取销售记录失败: {e}")
            raise

class DuozhuayuCrawler:
    """多抓鱼爬虫"""
    
    def __init__(self):
        self.inventory_repo = BookInventoryRepository()
    
    async def search_book_price(self, isbn: str) -> Dict[str, any]:
        """搜索多抓鱼的书籍价格"""
        # 多抓鱼API接口（示例，实际需要根据网站分析）
        search_url = f"https://www.duozhuayu.com/api/search?q={isbn}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and data.get('items'):
                            item = data['items'][0]
                            return {
                                'new_price': item.get('new_price'),
                                'second_hand_price': item.get('second_hand_price'),
                                'in_stock': item.get('in_stock', False),
                                'url': item.get('url')
                            }
            except Exception as e:
                logger.error(f"查询多抓鱼价格失败: {e}")
        
        return {}
    
    async def update_book_price(self, isbn: str, shop_id: int) -> bool:
        """更新书籍的多抓鱼价格"""
        # 获取书籍信息
        from ..models.repositories import BookRepository
        book_repo = BookRepository()
        book = book_repo.get_by_isbn(isbn)
        
        if not book:
            return False
        
        # 查询多抓鱼价格
        price_info = await self.search_book_price(isbn)
        
        if price_info:
            # 获取现有库存信息
            inventory = self.inventory_repo.get_by_book_shop(isbn, shop_id)
            
            if inventory:
                # 更新多抓鱼价格信息
                inventory['duozhuayu_new_price'] = price_info.get('new_price')
                inventory['duozhuayu_second_hand_price'] = price_info.get('second_hand_price')
                inventory['duozhuayu_in_stock'] = price_info.get('in_stock', False)
                inventory['duozhuayu_book_url'] = price_info.get('url')
                
                # 重新计算价差
                if inventory['kongfuzi_price'] and inventory['duozhuayu_second_hand_price']:
                    inventory['price_diff_second_hand'] = inventory['duozhuayu_second_hand_price'] - inventory['kongfuzi_price']
                    inventory['profit_margin_second_hand'] = (inventory['price_diff_second_hand'] / inventory['kongfuzi_price']) * 100
                    inventory['is_profitable'] = inventory['price_diff_second_hand'] > 0
                
                # 保存更新
                from ..models.models import BookInventory
                inv_model = BookInventory(**inventory)
                self.inventory_repo.upsert(inv_model)
                return True
        
        return False

class CrawlerManager:
    """爬虫管理器 - 统一管理所有爬虫"""
    
    def __init__(self):
        self.kongfuzi = KongfuziCrawler()
        self.duozhuayu = DuozhuayuCrawler()
        self.task_repo = CrawlTaskRepository()
    
    async def run_pending_tasks(self):
        """运行待执行的任务"""
        tasks = self.task_repo.get_pending_tasks()
        
        for task in tasks:
            try:
                if task['task_type'] == 'shop_books':
                    # 爬取店铺书籍
                    await self.kongfuzi.crawl_shop_books(task['target_url'])
                elif task['task_type'] == 'book_sales':
                    # 爬取销售记录
                    params = json.loads(task['task_params']) if task['task_params'] else {}
                    isbn = params.get('isbn')
                    if isbn:
                        await self.kongfuzi.crawl_book_sales(isbn)
                elif task['task_type'] == 'duozhuayu_price':
                    # 更新多抓鱼价格
                    params = json.loads(task['task_params']) if task['task_params'] else {}
                    isbn = params.get('isbn')
                    shop_id = params.get('shop_id')
                    if isbn and shop_id:
                        await self.duozhuayu.update_book_price(isbn, shop_id)
            except Exception as e:
                logger.error(f"执行任务 {task['id']} 失败: {e}")
                self.task_repo.update_status(task['id'], 'failed', error_message=str(e))
    
    async def cleanup(self):
        """清理资源"""
        await self.kongfuzi.disconnect_browser()